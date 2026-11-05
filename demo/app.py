import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
from google import genai

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

# FRED API Key 設定
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

# Gemini API Key 設定 (使用 google-genai)
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_key = st.sidebar.text_input("請輸入你的 Gemini API Key:", type="password", help="用於產生 AI 總經短評")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據 (設快取 1 小時)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "2年期美債殖利率": fred.get_series("DGS2"),
        "美國失業率": fred.get_series("UNRATE"),
        "聯邦基金利率": fred.get_series("FEDFUNDS"),
        "日本10年期國債殖利率": fred.get_series("IRLTLT01JPM156N")
    }
    df = pd.DataFrame(data).ffill().tail(365)
    
    # 計算 10 年期減 2 年期美債殖利率利差
    df["美債10Y-2Y利差"] = df["10年期美債殖利率"] - df["2年期美債殖利率"]
    return df

# 2. 抓取 Market 數據 (設快取 10 分鐘)
@st.cache_data(ttl=600)
def get_market_data():
    tickers = {
        "S&P 500": "^GSPC",
        "台灣加權指數": "^TWII",
        "布蘭特原油": "BZ=F",
        "美元/台幣匯率": "TWD=X",
        "黃金現貨價格": "GC=F"
    }
    df = yf.download(list(tickers.values()), period="1y")["Close"]
    df.rename(columns={v: k for k, v in tickers.items()}, inplace=True)
    return df

# 頁面渲染邏輯
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：關鍵總體經濟指標與利差監控 (FRED)
        st.subheader("📊 關鍵總體經濟指標與利差監控 (FRED)")
        
        # 取得最新利差數據以進行警示判斷
        latest_spread = macro_df["美債10Y-2Y利差"].dropna().iloc[-1]
        spread_prev = macro_df["美債10Y-2Y利差"].dropna().iloc[-2]

        # 殖利率曲線倒掛警示燈號
        if latest_spread < 0:
            st.warning(f"⚠️ **【警示】美債 10Y-2Y 殖利率曲線出現倒掛！** 目前利差為 **{latest_spread:.2f}%**（小於 0）。歷史經驗顯示這往往是經濟衰退的領先指標，請留意市場風險。")
        else:
            st.success(f"✅ **美債 10Y-2Y 殖利率曲線正常**：目前利差為 **{latest_spread:.2f}%**（大於等於 0）。")

        # 總經 KPI 網格 (6 欄位)
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        latest_cpi = macro_df["CPI 物價指數"].dropna().iloc[-1]
        col1.metric("CPI 物價指數", f"{latest_cpi:.1f}")
        
        latest_10y = macro_df["10年期美債殖利率"].dropna().iloc[-1]
        rate_prev_10y = macro_df["10年期美債殖利率"].dropna().iloc[-2]
        col2.metric("10年美債殖利率", f"{latest_10y:.2f}%", f"{latest_10y - rate_prev_10y:+.2f}%")
        
        latest_2y = macro_df["2年期美債殖利率"].dropna().iloc[-1]
        rate_prev_2y = macro_df["2年期美債殖利率"].dropna().iloc[-2]
        col3.metric("2年美債殖利率", f"{latest_2y:.2f}%", f"{latest_2y - rate_prev_2y:+.2f}%")

        col4.metric("10Y-2Y 利差", f"{latest_spread:.2f}%", f"{latest_spread - spread_prev:+.2f}%")

        latest_unemp = macro_df["美國失業率"].dropna().iloc[-1]
        col5.metric("美國失業率", f"{latest_unemp:.1f}%")
        
        latest_fed = macro_df["聯邦基金利率"].dropna().iloc[-1]
        col6.metric("聯邦基金利率", f"{latest_fed:.2f}%")

        # 第二區塊：主要金融市場即時報價 (yfinance)
        st.write("---")
        st.subheader("💰 主要金融市場即時報價 (yfinance)")
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

        def render_market_metric(col, df, col_name, fmt="{:.2f}" ):
            series = df[col_name].dropna()
            if len(series) >= 2:
                latest = series.iloc[-1]
                prev = series.iloc[-2]
                col.metric(col_name, fmt.format(latest), f"{latest - prev:+.2f}")
            elif len(series) == 1:
                col.metric(col_name, fmt.format(series.iloc[-1]))
            else:
                col.metric(col_name, "N/A")

        render_market_metric(m_col1, market_df, "S&P 500", "{:.1f}")
        render_market_metric(m_col2, market_df, "台灣加權指數", "{:.1f}")
        render_market_metric(m_col3, market_df, "布蘭特原油", "${:.2f}")
        render_market_metric(m_col4, market_df, "黃金現貨價格", "${:.1f}")
        render_market_metric(m_col5, market_df, "美元/台幣匯率", "{:.2f}")

        # 第三區塊：互動式圖表
        st.write("---")
        st.subheader("📈 市場走勢與總體指標折線圖")
        
        tab1, tab2 = st.tabs(["金融市場走勢 (yfinance)", "總體經濟趨勢 (FRED)"])
        
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns, key="market_select")
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns, key="macro_select")
            if macro_choice == "美債10Y-2Y利差":
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢（負值代表倒掛）")
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
            else:
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
                
            st.plotly_chart(fig2, use_container_width=True)

        # 第四區塊：AI 總體經濟摘要 (使用 google-genai)
        st.write("---")
        st.subheader("🤖 AI 總體經濟即時短評")
        
        if st.button("產生 AI 總體經濟摘要", type="primary"):
            if not gemini_key:
                st.error("請先在左側側邊欄輸入您的 Gemini API Key，才能使用 AI 摘要功能！")
            else:
                with st.spinner("AI 正在分析最新總體經濟與市場數據中..."):
                    try:
                        # 初始化 google-genai Client
                        client = genai.Client(api_key=gemini_key)
                        
                        latest_jp = macro_df["日本10年期國債殖利率"].dropna().iloc[-1]
                        
                        prompt = f"""
                        你是一位專業的總體經濟學家與金融分析師。請根據以下最新的美國與全球總經數據，為投資人撰寫一份約 200 字的繁體中文總體經濟短評，分析當前經濟情勢與潛在投資風險：
                        - CPI 物價指數: {latest_cpi:.1f}
                        - 10年期美債殖利率: {latest_10y:.2f}%
                        - 2年期美債殖利率: {latest_2y:.2f}%
                        - 10Y-2Y 美債利差: {latest_spread:.2f}% ({'已出現殖利率倒掛' if latest_spread < 0 else '維持正常'})
                        - 美國失業率: {latest_unemp:.1f}%
                        - 聯邦基金利率: {latest_fed:.2f}%
                        - 日本 10 年期國債殖利率: {latest_jp:.2f}%
                        
                        請確保語氣專業客觀、觀點精闢，排版清晰。
                        """
                        
                        # 呼叫最新 gemini-2.5-flash 模型
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=prompt,
                        )
                        
                        st.success("✨ AI 總經短評生成完畢：")
                        st.markdown(response.text)
                        
                    except Exception as e:
                        st.error(f"AI 摘要生成失敗，請確認 Gemini API Key 是否正確。錯誤訊息: {e}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
