import streamlit as st
import pandas as pd
import io

# 設定頁面配置
st.set_page_config(page_title="教科書單價計算機", layout="wide")

st.title("📚 教科書單價查詢與計算系統")
st.markdown("---")

# --- 功能 1: 生成範例檔案 ---
def generate_example_file():
    # 根據您提供的 PDF 內容建立範例數據
    # 參考  國小數學與  國中數學的價格結構
    data = [
        # 國小範例 (參考來源: 114學年度國小價格表)
        {"年級": "1", "科目": "數學", "冊別": "2", "出版社": "康軒", "課本價格": 110, "習作價格": 222},
        {"年級": "1", "科目": "數學", "冊別": "2", "出版社": "翰林", "課本價格": 98,  "習作價格": 236},
        {"年級": "1", "科目": "數學", "冊別": "2", "出版社": "南一", "課本價格": 107, "習作價格": 213},
        {"年級": "3", "科目": "英語", "冊別": "2", "出版社": "康軒", "課本價格": 100, "習作價格": 34}, # Wonder World
        
        # 國中範例 (參考來源: 114學年度國中價格表)
        {"年級": "7", "科目": "國文", "冊別": "2", "出版社": "翰林", "課本價格": 127, "習作價格": 76},
        {"年級": "7", "科目": "國文", "冊別": "2", "出版社": "南一", "課本價格": 145, "習作價格": 78},
        {"年級": "8", "科目": "理化", "冊別": "4", "出版社": "康軒", "課本價格": 149, "習作價格": 58},
        
        # 閩南語/客語範例 (參考來源: 114學年度非審定本)
        {"年級": "國小", "科目": "閩南語", "冊別": "2", "出版社": "真平", "課本價格": 135, "習作價格": 0},
        {"年級": "國中", "科目": "客語",   "冊別": "1", "出版社": "真平", "課本價格": 216, "習作價格": 0},
    ]
    df = pd.DataFrame(data)
    return df

st.sidebar.header("1. 下載範例與匯入資料")

# 準備範例檔案供下載
example_df = generate_example_file()
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    example_df.to_excel(writer, index=False)
    
st.sidebar.download_button(
    label="📥 下載標準範例檔 (Excel)",
    data=buffer.getvalue(),
    file_name="教科書單價表_範例.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    help="點擊下載範例，填入您的資料後再上傳。"
)

# --- 功能 2: 匯入資料 ---
uploaded_file = st.sidebar.file_uploader("上傳您的單價表 (Excel/CSV)", type=["xlsx", "csv"])

df = None
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # 確保必要的欄位存在
        required_columns = ["年級", "科目", "冊別", "出版社", "課本價格", "習作價格"]
        if not all(col in df.columns for col in required_columns):
            st.error(f"上傳的檔案格式錯誤，請確保包含以下欄位：{required_columns}")
            df = None
        else:
            # 處理空值，將無習作的價格設為 0
            df["習作價格"] = df["習作價格"].fillna(0)
            df["課本價格"] = df["課本價格"].fillna(0)
            # 轉換為字串以方便篩選
            df["年級"] = df["年級"].astype(str)
            df["冊別"] = df["冊別"].astype(str)
            st.sidebar.success("✅ 資料匯入成功！")
            
    except Exception as e:
        st.error(f"讀取檔案失敗: {e}")

# --- 功能 3 & 4: 介面篩選與計算 ---
if df is not None:
    st.header("2. 查詢與計算")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        grade_list = sorted(df["年級"].unique())
        selected_grade = st.selectbox("選擇年級", grade_list)
        
    with col2:
        # 根據年級連動篩選科目
        subject_list = sorted(df[df["年級"] == selected_grade]["科目"].unique())
        selected_subject = st.selectbox("選擇科目", subject_list)
        
    with col3:
        # 根據前兩項篩選冊別
        vol_list = sorted(df[(df["年級"] == selected_grade) & (df["科目"] == selected_subject)]["冊別"].unique())
        selected_vol = st.selectbox("選擇冊別", vol_list)
        
    with col4:
        # 最後篩選出版社
        publisher_list = sorted(df[(df["年級"] == selected_grade) & 
                                   (df["科目"] == selected_subject) & 
                                   (df["冊別"] == selected_vol)]["出版社"].unique())
        selected_publisher = st.selectbox("選擇出版社", publisher_list)

    # --- 輸出結果 ---
    st.markdown("### 💰 查詢結果")
    
    # 抓取對應的資料列
    result_row = df[
        (df["年級"] == selected_grade) & 
        (df["科目"] == selected_subject) & 
        (df["冊別"] == selected_vol) & 
        (df["出版社"] == selected_publisher)
    ]

    if not result_row.empty:
        textbook_price = float(result_row.iloc[0]["課本價格"])
        workbook_price = float(result_row.iloc[0]["習作價格"])
        total_price = textbook_price + workbook_price
        
        m1, m2, m3 = st.columns(3)
        m1.metric("📖 課本價格", f"${textbook_price:,.0f}")
        m2.metric("✍️ 習作價格", f"${workbook_price:,.0f}")
        m3.metric("💵 合計金額", f"${total_price:,.0f}", delta_color="normal")
        
        if workbook_price == 0:
            st.info("💡 此項目顯示習作價格為 $0，可能該版本無習作或未輸入價格。")
    else:
        st.warning("查無資料，請檢查篩選條件。")

    # --- 顯示原始資料預覽 ---
    with st.expander("查看目前匯入的完整資料表"):
        st.dataframe(df)

else:
    st.info("👋 請從左側側邊欄下載範例檔，填寫後上傳以開始使用。")
    st.markdown("""
    ### 使用說明
    1. 點擊左側 **「下載標準範例檔」**。
    2. 開啟 Excel 檔案，依照格式輸入書籍資料（可參考  國小價格表 或  國中價格表）。
    3. 將整理好的檔案拖曳至左側 **「上傳您的單價表」** 區域。
    4. 在上方選單選擇 **年級、科目、冊別、出版社**。
    5. 系統將自動計算並顯示總價。
    """)
