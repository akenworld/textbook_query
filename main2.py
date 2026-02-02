import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
import csv
from collections import defaultdict

# --- 頁面設定 ---
st.set_page_config(page_title="教科書價格查詢系統", layout="wide")

# --- 核心邏輯函數 ---
def extract_price(t):
    """
    修正核心：針對國中版 PDF 內容如 "075\n" 或 ",75" 進行過濾
    """
    if t is None: return 0
    # 移除所有非數字的字元（包含換行 \n、逗號、空格等）
    cleaned = re.sub(r'[^\d]', '', str(t).strip())
    # 轉為整數，自動處理字首 0（例如 "075" 會變成 75）
    return int(cleaned) if cleaned else 0

def get_subject_weight(sub_name):
    """
    排序邏輯：讓常見科目在下拉選單中排在前面
    """
    sort_order = ["國語", "國文", "數學", "生活", "社會", "自然", "藝術", "健體", "健康", "綜合", "英語", "英文"]
    for i, keyword in enumerate(sort_order):
        if keyword in sub_name: return i
    return 999

def parse_pdf(file):
    """
    PDF 解析邏輯：自動偵測出版社欄位與表格內容
    """
    db = {}
    detected_vers = []
    # 擴充出版社清單，涵蓋國中小常用廠商
    target_publishers = ["南一", "康軒", "翰林", "育成", "佳音", "何嘉仁", "吉的堡", "台灣培生", "全華", "龍騰", "泰宇", "三民"]
    col_map = {"年級": 2, "科目": 1, "冊別": 3}
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table[0]) < 4: continue
                
                # 1. 偵測欄位索引（掃描前幾行找出年級、科目、出版社位置）
                for r_idx in range(min(15, len(table))):
                    row = table[r_idx]
                    for i, cell in enumerate(row):
                        txt = str(cell or "").replace("\n", "").strip()
                        for k in target_publishers:
                            if k in txt and (k, i) not in detected_vers:
                                detected_vers.append((k, i))
                        if "年級" in txt: col_map["年級"] = i
                        if any(x in txt for x in ["科目", "學習領域", "學科"]): col_map["科目"] = i
                        if "冊" in txt: col_map["冊別"] = i
                
                # 2. 解析資料列
                for row in table:
                    row_str = "".join([str(c) for c in row if c])
                    # 判斷是否為課本或習作行
                    if "課本" in row_str or "習作" in row_str:
                        if row[col_map["科目"]] and row[col_map["年級"]]:
                            # 清理科目名稱（移除數字編號與換行）
                            raw_s = str(row[col_map["科目"]]).strip().replace("\n", "")
                            s_name = re.sub(r'^\d+\s*|\s*\d+$', '', raw_s)
                            
                            # 讀取年級與冊別
                            g_name = str(row[col_map["年級"]]).strip().replace("\n", "")
                            v_name = str(row[col_map["冊別"]]).strip().replace("\n", "")
                            
                            key = (g_name, s_name, v_name)
                            cat = "課" if "課本" in row_str else "習"
                            
                            price_dict = {}
                            for ver_name, col_idx in detected_vers:
                                if col_idx < len(row):
                                    price_dict[ver_name] = extract_price(row[col_idx])
                            
                            if key not in db: db[key] = {"課": {}, "習": {}}
                            db[key][cat].update(price_dict)
    
    # 依照欄位順序排列版本
    versions = [v[0] for v in sorted(detected_vers, key=lambda x: x[1])]
    return db, versions

# --- 初始化 Session State ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'db' not in st.session_state:
    st.session_state.db = None
if 'versions' not in st.session_state:
    st.session_state.versions = []
if 'pdf_name' not in st.session_state:
    st.session_state.pdf_name = ""

# --- 側邊欄 ---
st.sidebar.title("🛠️ 控制面板")

# 1. PDF 上傳
uploaded_pdf = st.sidebar.file_uploader("1. 載入價格 PDF ", type="pdf")
if uploaded_pdf:
    if uploaded_pdf.name != st.session_state.pdf_name:
        with st.spinner("正在解析 PDF (包含個位數修正邏輯)..."):
            db, versions = parse_pdf(uploaded_pdf)
            st.session_state.db = db
            st.session_state.versions = versions
            st.session_state.pdf_name = uploaded_pdf.name
            st.sidebar.success(f"解析完成！共有 {len(db)} 筆資料項目")

# 下載範例檔 (已更新為包含 1-9 年級的格式)
template_csv = "教科書一覽表,,,,,,,,,\n科目/年級,一年級,二年級,三年級,四年級,五年級,六年級,七年級,八年級,九年級\n國語/國文,,,,,,,,,\n數學,,,,,,,,,\n生活,,,,,,,,,\n健康與體育,,,,,,,,,\n自然科學,,,,,,,,,\n社會,,,,,,,,,\n英語,,,,,,,,,\n綜合活動,,,,,,,,,\n藝術,,,,,,,,,\n"
st.sidebar.download_button("📥 下載版本一覽表範例檔", data=template_csv.encode('utf-8-sig'), file_name="教科書版本一覽表(範例檔).csv", mime="text/csv")

# 2. CSV 自動匯入
uploaded_csv = st.sidebar.file_uploader("2. 匯入選用一覽表 (CSV)", type="csv")
if uploaded_csv and st.session_state.db:
    if st.sidebar.button("🚀 執行自動匯入"):
        try:
            raw_data = uploaded_csv.getvalue().decode('utf-8-sig')
            df_full = pd.read_csv(io.StringIO(raw_data))
            
            # 自動找尋標題列
            header_idx = 0
            for i, row in df_full.iterrows():
                if any("年級" in str(cell) for cell in row):
                    header_idx = i
                    break
            
            df = pd.read_csv(io.StringIO(raw_data), header=header_idx + 1)
            # 支援國中小多種年級寫法
            grade_cols = {
                "一年級":"1", "二年級":"2", "三年級":"3", "四年級":"4", "五年級":"5", "六年級":"6",
                "七年級":"7", "八年級":"8", "九年級":"9", "初一":"7", "初二":"8", "初三":"9"
            }
            
            items_added = 0
            for _, row in df.iterrows():
                # 處理科目名稱比對 (移除斜線與空格)
                subject_raw = str(row[0]).strip()
                if not subject_raw or subject_raw == "nan": continue
                
                for g_zh, g_num in grade_cols.items():
                    if g_zh in df.columns:
                        version = str(row[g_zh]).strip()
                        if version and version != "nan" and version != "":
                            # 尋找冊別（模糊匹配科目名稱）
                            matched_keys = [k for k in st.session_state.db.keys() if k[0] == g_num and (k[1] in subject_raw or subject_raw in k[1])]
                            vols = sorted(list(set([k[2] for k in matched_keys])))
                            
                            if vols:
                                target_vol = vols[0]
                                actual_subject = [k[1] for k in matched_keys if k[2] == target_vol][0]
                                
                                res = st.session_state.db.get((g_num, actual_subject, target_vol), {})
                                pb = res.get("課", {}).get(version, 0)
                                pw = res.get("習", {}).get(version, 0)
                                if pb > 0 or pw > 0:
                                    st.session_state.cart.append({
                                        "年級": f"{g_num}年", "科目": actual_subject, "版本": version, 
                                        "冊別": target_vol, "課本": pb, "習作": pw, "小計": pb+pw
                                    })
                                    items_added += 1
            st.sidebar.success(f"匯入成功！已從「{uploaded_csv.name}」帶入 {items_added} 筆資料。")
        except Exception as e:
            st.sidebar.error(f"匯入發生錯誤：{e}")

# --- 主介面 ---
st.title("📚 教科書價格查詢系統 ")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 手動新增")
    if st.session_state.db:
        # 動態選項連動
        grades = sorted(list(set([k[0] for k in st.session_state.db.keys()])))
        grade = st.selectbox("選擇年級", grades)
        
        subjects = sorted(list(set([k[1] for k in st.session_state.db.keys() if k[0] == grade])), key=get_subject_weight)
        subject = st.selectbox("選擇科目", subjects)
        
        vols = sorted(list(set([k[2] for k in st.session_state.db.keys() if k[0] == grade and k[1] == subject])))
        vol = st.selectbox("選擇冊別", vols)
        
        version = st.radio("選擇版本", st.session_state.versions, horizontal=True)
        
        if st.button("➕ 加入清單"):
            res = st.session_state.db.get((grade, subject, vol), {})
            pb = res.get("課", {}).get(version, 0)
            pw = res.get("習", {}).get(version, 0)
            st.session_state.cart.append({"年級": f"{grade}年", "科目": subject, "版本": version, "冊別": vol, "課本": pb, "習作": pw, "小計": pb+pw})
    else:
        st.info("💡 請先從左側上傳價格 PDF。 ")

with col2:
    st.subheader("📋 查詢清單")
    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart, use_container_width=True)
        if st.button("🔄 清空清單"):
            st.session_state.cart = []
            st.rerun()
    else:
        st.write("清單目前為空。")

# --- 報表匯出 ---
if st.session_state.cart:
    st.divider()
    st.subheader("📊 報表匯出")
    
    grade_groups = defaultdict(list)
    grade_totals = defaultdict(int)
    for item in st.session_state.cart:
        grade_groups[item['年級']].append(item)
        grade_totals[item['年級']] += item['小計']
    
    output = io.StringIO()
    writer = csv.writer(output)
    sorted_grades = sorted(grade_groups.keys())
    
    # 年級標題列
    h_row = []
    for g in sorted_grades: h_row += [f"【{g}】", "", "", "", ""]
    writer.writerow(h_row)

    # 總計置頂列
    total_row = []
    for g in sorted_grades: total_row += ["★年級總計", "", "", grade_totals[g], ""]
    writer.writerow(total_row)
    writer.writerow([])
    
    # 填充明細
    max_b = max(len(grade_groups[g]) for g in sorted_grades)
    for b_idx in range(max_b):
        r1, r2, r3 = [], [], []
        for g in sorted_grades:
            books = grade_groups[g]
            if b_idx < len(books):
                b = books[b_idx]
                r1 += ["科目", b['科目'], "課本", b['課本'], ""]
                r2 += ["版本", b['版本'], "習作", b['習作'], ""]
                r3 += ["冊別", b['冊別'], "小計", b['小計'], ""]
            else:
                r1 += [""]*5; r2 += [""]*5; r3 += [""]*5
        writer.writerow(r1); writer.writerow(r2); writer.writerow(r3); writer.writerow([])
        
    st.download_button("💾 下載費用明細表 (CSV)", 
                       data=output.getvalue().encode('utf-8-sig'), 
                       file_name="教科書費用明細表.csv", 
                       mime="text/csv")
