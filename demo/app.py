import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from fredapi import Fred
import feedparser
import google.generativeai as genai
from urllib.parse import quote  # 解決 URL 空白字元轉碼問題

# ==========================================
# 1. 頁面配置與側邊欄金鑰設定
# ==========================================
st.set_page_config(page_title="總體經濟、金融與 AI 智慧儀表板", layout="wide")
st.title("🌐 全球總體經濟、金融指標與 AI 智慧互動儀表板")

st.sidebar.header("⚙️ 設定與金鑰")

# 1.1 檢查 FRED API Key
if "FRED_API_KEY" in st.secrets:
    fred_key = st.secrets["FRED_API_KEY"]
    st.sidebar.success("已自動讀取 FRED API Key！")
else:
    fred_key = st.sidebar.text_input("請輸入 FRED API Key:", type="password")

# 1.2 檢查 Gemini API Key (NLP 與聊天室用)
gemini_key = None
if "GEMINI_API_KEY" in st.secrets:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=gemini_key)
    st.sidebar.success("已自動讀取 Gemini API Key！")
else:
    gemini_input = st.sidebar.text_input("請輸入 Gemini API Key:", type="password")
    if gemini_input:
        gemini_key = gemini_input
        genai.configure(api_key=gemini_key)

if st.sidebar.button("手動刷新數據"):
    st.cache_data.clear()

# ==========================================
# 2. 數據抓取函式 (FRED, yfinance, RSS 新聞)
# ==========================================
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
    df["美債10Y-2Y利差"] = df["10年期美債殖利率"] - df["2年期美債殖利率"]
    return df

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

@st.cache_data(ttl=1800)
def fetch_google_news(keyword="Federal Reserve Inflation"):
    safe_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={safe_keyword}&hl=en-US"
    feed = feedparser.parse(url)
    return [entry.title for entry in feed.entries[:8]]

# ==========================================
# 3. 頁面渲染邏輯
# ==========================================
if fred_key:
    try:
        macro_df = get_fred_data(fred_key)
        market_df = get_market_data()

        # 第一區塊：核心總經 KPI 卡片與利差監控
        st.subheader("📊 關鍵總體經濟指標與利差監控 (FRED)")
        
        latest_spread = macro_df["美債10Y-2Y利差"].dropna().iloc[-1]
        spread_prev = macro_df["美債10Y-2Y利差"].dropna().iloc[-2]

        if latest_spread < 0:
            st.warning(f"⚠️ **【警示】美債 10Y-2Y 殖利率曲線出現倒掛！** 目前利差為 **{latest_spread:.2f}%**（小於 0）。歷史經驗顯示這往往是經濟衰退的領先指標，請留意市場風險。")
        else:
            st.success(f"✅ **美債 10Y-2Y 殖利率曲線正常**：目前利差為 **{latest_spread:.2f}%**（大於等於 0）。")

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

        st.write("---")

        # 第二區塊：多分頁儀表板（新增相關係數與 AI 聊天室）
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 金融市場走勢", 
            "🏛️ 總體經濟趨勢", 
            "🔗 多資產相關係數熱力圖", 
            "📰 新聞輿論與鷹鴿情緒",
            "💬 AI 總經與數據對話室"
        ])
        
        # 頁籤 1: 金融市場走勢
        with tab1:
            market_choice = st.selectbox("選擇金融市場標的：", market_df.columns, key="market_choice_tab1")
            fig1 = px.line(market_df, y=market_choice, title=f"{market_choice} 近一年走勢")
            st.plotly_chart(fig1, use_container_width=True)
            
        # 頁籤 2: 總體經濟趨勢
        with tab2:
            macro_choice = st.selectbox("選擇總體經濟指標：", macro_df.columns, key="macro_choice_tab2")
            if macro_choice == "美債10Y-2Y利差":
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢（負值代表倒掛）")
                fig2.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="倒掛分界線 (0%)")
            else:
                fig2 = px.line(macro_df, y=macro_choice, title=f"{macro_choice} 近一年走勢")
            st.plotly_chart(fig2, use_container_width=True)

        # 頁籤 3: 多資產相關係數熱力圖 (New!)
        with tab3:
            st.subheader("🔗 總經指標與金融資產相關係數矩陣")
            st.markdown("透過對齊時間序列，觀察各項總經數據與金融資產（如美債、S&P 500、黃金、原油）之間的連動與互補關係。")
            
            # 合併總經與市場數據並計算相關係數
            combined_df = pd.concat([macro_df, market_df], axis=1).dropna()
            corr_matrix = combined_df.corr()
            
            fig_corr = px.imshow(
                corr_matrix, 
                text_auto=".2f", 
                aspect="auto", 
                color_continuous_scale="RdBu_r", 
                range_color=[-1, 1],
                title="總體經濟與金融資產相關性熱力圖"
            )
            st.plotly_chart(fig_corr, use_container_width=True)

        # 頁籤 4: 新聞輿論與情緒分析
        with tab4:
            st.subheader("📰 即時財經新聞與 LLM 鷹鴿派情緒分析")
            
            search_kw = st.text_input("🔍 輸入新聞關鍵字:", value="Federal Reserve Inflation")
            news_titles = fetch_google_news(search_kw)

            nlp_col1, nlp_col2 = st.columns([1, 1])

            with nlp_col1:
                st.markdown("### 📌 最新財經新聞標題 (RSS)")
                if news_titles:
                    for i, title in enumerate(news_titles, 1):
                        st.write(f"**{i}.** {title}")
                else:
                    st.warning("查無相關新聞標題。")

            with nlp_col2:
                st.markdown("### 🤖 Gemini AI 鷹鴿派與情緒打分")
                if gemini_key:
                    if st.button("🚀 開始分析新聞市場情緒", type="primary"):
                        if news_titles:
                            with st.spinner("Gemini 正在剖析文本立場與鷹鴿情緒中..."):
                                try:
                                    news_text = "\n".join([f"- {t}" for t in news_titles])
                                    prompt = f"""你是一位專業總體經濟分析師。請分析以下 8 條新聞標題：
{news_text}

請以繁體中文輸出結構化報告：
1. 整體市場情緒分數 (0~100)
2. 貨幣政策立場判定 (鷹派/鴿派/中立)
3. 重點分析與逐條評分表格 (Markdown Format)"""
                                    
                                    model = genai.GenerativeModel("gemini-3.8-flash")
                                    response = model.generate_content(prompt)
                                    st.markdown(response.text)
                                except Exception as e:
                                    if "503" in str(e) or "UNAVAILABLE" in str(e):
                                        st.warning("⚠️ **Google 伺服器目前流量較大**，請稍候再試！")
                                    else:
                                        st.error(f"AI 分析時發生錯誤: {e}")
                        else:
                            st.warning("尚無新聞數據。")
                else:
                    st.warning("👈 請在側邊欄輸入 Gemini API Key 以啟用 AI 分析。")

        # 頁籤 5: AI 總經與數據對話室 (New!)
        with tab5:
            st.subheader("💬 AI 總經與數據諮詢助理")
            st.markdown("你可以直接向 AI 詢問當前儀表板中的數據代表什麼意義，或探討總體經濟情勢（例如：*「目前的 10Y-2Y 利差代表什麼？對股市有何影響？」*）。")
            
            if not gemini_key:
                st.warning("👈 請先在側邊欄輸入 Gemini API Key，才能使用對話機器人功能。")
            else:
                # 初始化聊天記錄
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                # 顯示歷史對話
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                # 使用者輸入框
                if user_query := st.chat_input("向 AI 提問有關總經或金融市場的問題..."):
                    st.session_state.messages.append({"role": "user", "content": user_query})
                    with st.chat_message("user"):
                        st.markdown(user_query)

                    with st.chat_message("assistant"):
                        with st.spinner("AI 正在思考中..."):
                            try:
                                # 將當前儀表板的即時數據作為 Context 注入系統提示詞中
                                context_info = f"""
                                當前儀表板抓取到的最新即時總經與市場數據如下：
                                - CPI 物價指數: {latest_cpi:.1f}
                                - 10年期美債殖利率: {latest_10y:.2f}%
                                - 2年期美債殖利率: {latest_2y:.2f}%
                                - 10Y-2Y 美債利差: {latest_spread:.2f}% ({'已倒掛' if latest_spread < 0 else '正常'})
                                - 美國失業率: {latest_unemp:.1f}%
                                - 聯邦基金利率: {latest_fed:.2f}%
                                """
                                
                                chat_model = genai.GenerativeModel(
                                    model_name="gemini-3.8-flash",
                                    system_instruction=f"你是一位專業的總體經濟學家與金融分析師。請結合以下即時數據來回答使用者的問題：\n{context_info}"
                                )
                                
                                # 組合對話歷史
                                history_for_gemini = [
                                    {"role": m["role"] if m["role"] == "user" else "model", "parts": [m["content"]]}
                                    for m in st.session_state.messages
                                ]
                                
                                chat = chat_model.start_chat(history=history_for_gemini[:-1])
                                response = chat.send_message(user_query)
                                
                                ai_reply = response.text
                                st.markdown(ai_reply)
                                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                                
                            except Exception as e:
                                st.error(f"對話產生錯誤: {e}")

    except Exception as e:
        st.error(f"數據讀取失敗，請確認 FRED API Key 是否正確。錯誤訊息: {e}")
else:
    st.info("👈 請在左側輸入您的 FRED API Key 以開啟儀表板。")
