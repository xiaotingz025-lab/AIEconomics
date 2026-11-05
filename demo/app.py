import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred

# 頁面基本配置
st.set_page_config(page_title="總體經濟與金融即時儀表板", layout="wide")
st.title("🌐 全球總體經濟與金融指標即時儀表板")

# 側邊欄：輸入 API Key 與刷新控制
st.sidebar.header("⚙️ 設定與金鑰")

if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 Secrets 中的 API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入你的 FRED API Key:", type="password")

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# 1. 抓取 FRED 數據 (設快取 1 小時)
@st.cache_data(ttl=3600)
def get_fred_data(api_key):
    fred = Fred(api_key=api_key)
    data = {
        "CPI 物價指數": fred.get_series("CPIAUCSL"),
        "10年期美債殖利率": fred.get_series("DGS10"),
        "2年期美債殖利率": fred.get_series("DGS2"),         # 新增：2年期美債殖利率
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

        # 第一區塊：關鍵總體經濟指標 (FRED) - 佈局調整
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
            
            # 如果選擇了利差，可以額外加上一條 0 軸參考線讓畫面更直覺
            if macro_choice == "美債10Y-2Y利差":
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢（負值代表倒掛）")
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
            else:
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
                
            st.plotly_chart(fig2, use_container_width=True)

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
