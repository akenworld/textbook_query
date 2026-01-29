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
    if not t or "-" in str(t): return 0
    m = re.search(r'\d+', str(t).replace('\n', '').replace(',', ''))
    return int(m.group()) if m else 0

def get_subject_weight(sub_name):
    sort_order = ["國語", "國文", "數學", "生活", "社會", "自然", "藝術", "健體", "健康", "綜合", "英語", "英文"]
    for i, keyword in enumerate(sort_order):
        if keyword in sub_name: return i
    return 999

def parse_pdf(file):
    db = {}
    detected_vers = []
    target_publishers = ["南一", "康軒", "翰林", "育成", "佳音", "何嘉仁", "吉的堡", "台灣培生", "全華", "龍騰", "泰宇", "三民"]
    col_map = {"年級": 2, "科目": 1, "冊別": 3}
    
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table[0]) < 4: continue
                for r_idx in range(min(10, len(table))):
                    row = table[r_idx]
                    for i, cell in enumerate(row):
                        txt = str(cell or "").replace("\n", "").strip()
                        for k in target_publishers:
                            if k in txt and (k, i) not in detected_vers:
                                detected_vers.append((k, i))
                        if "年級" in txt: col_map["年級"] = i
                        if "科目" in txt: col_map["科目"] = i
                        if "冊" in txt: col_map["冊別"] = i
                
                for row in table:
                    row_str = "".join([str(c) for c in row if c])
                    if "課本" in row_str or "習作" in row_str:
                        if row[col_map["科目"]] and row[col_map["年級"]]:
                            raw_s = str(row[col_map["科目"]]).strip()
                            s_name = re.sub(r'^\d+\s*|\s*\d+$', '', raw_s)
                            g_name = str(row[col_map["年級"]]).strip()
                            v_name = str(row[col_map["冊別"]]).strip()
                            key = (g_name, s_name, v_name)
                            cat = "課" if "課本" in row_str else "習"
                            
                            price_dict = {}
                            for ver_name, col_idx in detected_vers:
                                if col_idx < len(row):
                                    price_dict[ver_name] = extract_price(row[col_idx])
                            
                            if key not in db: db[key] = {"課": {}, "習": {}}
                            db[key][cat].update(price_dict)
    
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

# 增加監測檔案名稱變動的邏輯
uploaded_pdf = st.sidebar.file_uploader("1. 載入價格 PDF", type="pdf")

if uploaded_pdf:
    # 如果上傳的文件與快取中的名稱不同，視為重新載入，重設資料庫
    if uploaded_pdf.name != st.session_state.pdf_name:
        with st.spinner("偵測到新文件，重新解析 PDF 中..."):
            db, versions = parse_pdf(uploaded_pdf)
            st.session_state.db = db
            st.session_state.versions = versions
            st.session_state.pdf_name = uploaded_pdf.name
            st.sidebar.success(f"已更新資料庫：{uploaded_pdf.name}")

# 下載範例檔
template_csv = "教科書一覽表,,,,,,\n科目/年級,一年級,二年級,三年級,四年級,五年級,六年級\n國語,康軒,康軒,南一,康軒,南一,康軒\n數學,南一,南一,南一,南一,翰林,南一\n生活,翰林,翰林,,,,\n健康與體育,翰林,翰林,南一,康軒,南一,南一\n自然科學,,,南一,翰林,南一,翰林\n社會,,,康軒,康軒,南一,翰林\n英語,,,康軒,翰林,翰林,何嘉仁\n綜合活動,,,翰林,康軒,康軒,南一\n藝術,,,康軒,翰林,康軒,康軒\n"
st.sidebar.download_button("📥 下載一覽表範例檔", data=template_csv.encode('utf-8-sig'), file_name="範例檔.csv", mime="text/csv")

# 匯入一覽表
uploaded_csv = st.sidebar.file_uploader("2. 匯入選用一覽表 (CSV)", type="csv")
if uploaded_csv and st.session_state.db:
    if st.sidebar.button("🚀 執行自動匯入"):
        df = pd.read_csv(uploaded_csv, encoding='utf-8-sig', header=1)
        grade_cols = {"一年級":"1", "二年級":"2", "三年級":"3", "四年級":"4", "五年級":"5", "六年級":"6"}
        
        for _, row in df.iterrows():
            subject = str(row[0]).strip()
            for g_zh, g_num in grade_cols.items():
                if g_zh in df.columns:
                    version = str(row[g_zh]).strip()
                    if version and version != "nan" and version != "":
                        vols = sorted(list(set([k[2] for k in st.session_state.db.keys() if k[0] == g_num and k[1] == subject])))
                        if vols:
                            target_vol = ""
                            for v in vols:
                                if str(int(g_num)*2) in v: target_vol = v; break
                            if not target_vol: target_vol = vols[0]
                            
                            res = st.session_state.db.get((g_num, subject, target_vol), {})
                            pb = res.get("課", {}).get(version, 0)
                            pw = res.get("習", {}).get(version, 0)
                            st.session_state.cart.append({"年級": f"{g_num}年", "科目": subject, "版本": version, "冊別": target_vol, "課本": pb, "習作": pw, "小計": pb+pw})
        st.sidebar.success("匯入完成！")

# --- 主介面 ---
st.title("📚 教科書價格查詢系統")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 手動新增")
    if st.session_state.db:
        # 年級選項會根據 db 自動更新
        grades = sorted(list(set([k[0] for k in st.session_state.db.keys()])))
        grade = st.selectbox("選擇年級", grades)
        
        # 科目選項會根據選擇的年級從 db 動態抓取
        subjects = sorted(list(set([k[1] for k in st.session_state.db.keys() if k[0] == grade])), key=get_subject_weight)
        subject = st.selectbox("選擇科目", subjects)
        
        # 冊別選項同樣根據 db 動態抓取
        vols = sorted(list(set([k[2] for k in st.session_state.db.keys() if k[0] == grade and k[1] == subject])))
        vol = st.selectbox("選擇冊別", vols)
        
        # 版本會根據該 PDF 偵測到的出版社列出
        version = st.radio("選擇版本", st.session_state.versions, horizontal=True)
        
        if st.button("➕ 加入清單"):
            res = st.session_state.db.get((grade, subject, vol), {})
            pb = res.get("課", {}).get(version, 0)
            pw = res.get("習", {}).get(version, 0)
            st.session_state.cart.append({"年級": f"{grade}年", "科目": subject, "版本": version, "冊別": vol, "課本": pb, "習作": pw, "小計": pb+pw})
    else:
        st.info("請先從左側上傳價格 PDF 檔案以開啟查詢功能。")

with col2:
    st.subheader("📋 查詢清單")
    if st.session_state.cart:
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart, use_container_width=True)
        if st.button("🔄 清空清單"):
            st.session_state.cart = []
            st.rerun()

# --- 匯出報表邏輯 ---
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
    
    # 寫入第一行：年級標題
    h_row = []
    for g in sorted_grades:
        h_row += [f"【{g}】", "", "", "", ""]
    writer.writerow(h_row)

    # 寫入第二行：總計置頂
    total_row = []
    for g in sorted_grades:
        total_row += ["★年級總計", "", "", grade_totals[g], ""]
    writer.writerow(total_row)
    writer.writerow([])
    
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
        
    st.download_button("💾 下載費用明細表 (總計已置頂)", 
                       data=output.getvalue().encode('utf-8-sig'), 
                       file_name="教科書費用明細表.csv", 
                       mime="text/csv")
