import streamlit as st
import pdfplumber
import re
import pandas as pd
import io
import csv
from collections import defaultdict

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="教科書價格查詢系統", layout="wide")

# --- 2. 核心邏輯函數定義 (必須放在最前面) ---
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
                # 偵測欄位索引
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
                
                # 解析內容
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

# --- 3. 初始化 Session State ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'db' not in st.session_state:
    st.session_state.db = None
if 'versions' not in st.session_state:
    st.session_state.versions = []

# --- 4. 側邊欄：控制面板 ---
st.sidebar.title("🛠️ 控制面板")
uploaded_pdf = st.sidebar.file_uploader("1. 載入價格 PDF", type="pdf")

if uploaded_pdf:
    # 只有當 PDF 改變或尚未讀取時才解析
    if st.session_state.db is None:
        with st.spinner("解析 PDF 中..."):
            db_res, ver_res = parse_pdf(uploaded_pdf)
            st.session_state.db = db_res
            st.session_state.versions = ver_res
            st.sidebar.success("PDF 載入成功！")

# 下載範例檔
template_csv = "教科書一覽表,,,,,,\n科目/年級,一年級,二年級,三年級,四年級,五年級,六年級\n國語,康軒,康軒,南一,康軒,南一,康軒\n數學,南一,南一,南一,南一,翰林,南一\n生活,翰林,翰林,,,,\n健康與體育,翰林,翰林,南一,康軒,南一,南一\n自然科學,,,南一,翰林,南一,翰林\n社會,,,康軒,康軒,南一,翰林\n英語,,,康軒,翰林,翰林,何嘉仁\n綜合活動,,,翰林,康軒,康軒,南一\n藝術,,,康軒,翰林,康軒,康軒\n"
st.sidebar.download_button("📥 下載一覽表範例檔", data=template_csv.encode('utf-8-sig'), file_name="範例檔.csv", mime="text/csv")

# 匯入一覽表邏輯
uploaded_csv = st.sidebar.file_uploader("2. 匯入選用一覽表 (CSV)", type="csv")
if uploaded_csv and st.session_state.db:
    if st.sidebar.button("🚀 執行自動匯入"):
        # 讀取 CSV，跳過第一行標題，以第二行作為欄位名
        df_import = pd.read_csv(uploaded_csv, encoding='utf-8-sig', header=1)
        grade_cols = {"一年級":"1", "二年級":"2", "三年級":"3", "四年級":"4", "五年級":"5", "六年級":"6"}
        
        new_items = []
        for _, row in df_import.iterrows():
            subject = str(row[0]).strip()
            for g_zh, g_num in grade_cols.items():
                if g_zh in df_import.columns:
                    version = str(row[g_zh]).strip()
                    if version and version != "nan" and version != "":
                        vols = sorted(list(set([k[2] for k in st.session_state.db.keys() if k[0] == g_num and k[1] == subject])))
                        if vols:
                            target_vol = ""
                            for v in vols:
                                if str(int(g_num)*2) in v: target_vol = v; break
                            if not target_vol: target_vol = vols[0]
                            
                            res_price = st.session_state.db.get((g_num, subject, target_vol), {})
                            pb = res_price.get("課", {}).get(version, 0)
                            pw = res_price.get("習", {}).get(version, 0)
                            new_items.append({"年級": f"{g_num}年", "科目": subject, "版本": version, "冊別": target_vol, "課本": pb, "習作": pw, "小計": pb+pw})
        st.session_state.cart.extend(new_items)
        st.sidebar.success(f"匯入完成，新增了 {len(new_items)} 筆書目！")

# --- 5. 主介面展示 ---
st.title("📚 進階教科書價格查詢系統")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🔍 手動新增")
    if st.session_state.db:
        grades = sorted(list(set([k[0] for k in st.session_state.db.keys()])))
        grade_sel = st.selectbox("選擇年級", grades)
        
        subjects = sorted(list(set([k[1] for k in st.session_state.db.keys() if k[0] == grade_sel])), key=get_subject_weight)
        subject_sel = st.selectbox("選擇科目", subjects)
        
        vols = sorted(list(set([k[2] for k in st.session_state.db.keys() if k[0] == grade_sel and k[1] == subject_sel])))
        vol_sel = st.selectbox("選擇冊別", vols)
        
        ver_sel = st.radio("選擇版本", st.session_state.versions, horizontal=True)
        
        if st.button("➕ 加入清單"):
            res = st.session_state.db.get((grade_sel, subject_sel, vol_sel), {})
            pb = res.get("課", {}).get(ver_sel, 0)
            pw = res.get("習", {}).get(ver_sel, 0)
            st.session_state.cart.append({
                "年級": f"{grade_sel}年", "科目": subject_sel, "版本": ver_sel, 
                "冊別": vol_sel, "課本": pb, "習作": pw, "小計": pb+pw
            })
    else:
        st.info("請先從側邊欄上傳 PDF 價格表。")

with col2:
    st.subheader("📋 查詢清單")
    if st.session_state.cart:
        df_display = pd.DataFrame(st.session_state.cart)
        st.table(df_display)
        if st.button("🔄 清空清單"):
            st.session_state.cart = []
            st.rerun()
    else:
        st.write("目前清單中尚無書目。")

# --- 6. 報表匯出邏輯 (總計置頂) ---
if st.session_state.cart:
    st.divider()
    st.subheader("📊 報表匯出")
    
    grade_groups = defaultdict(list)
    grade_totals = defaultdict(int)
    for item in st.session_state.cart:
        grade_groups[item['年級']].append(item)
        grade_totals[item['年級']] += item['小計']
    
    # 使用 StringIO 生成 CSV
    output_buffer = io.StringIO()
    csv_writer = csv.writer(output_buffer)
    sorted_grades = sorted(grade_groups.keys())
    
    # 寫入年級標題
    csv_writer.writerow([f"【{g}】" for g in sorted_grades for _ in range(5)])
    # 寫入總計置頂
    csv_writer.writerow(["★年級總計", "", "", grade_totals[g], ""] * len(sorted_grades))
    csv_writer.writerow([])
    
    max_rows = max(len(grade_groups[g]) for g in sorted_grades)
    for r_idx in range(max_rows):
        row1, row2, row3 = [], [], []
        for g in sorted_grades:
            grade_items = grade_groups[g]
            if r_idx < len(grade_items):
                it = grade_items[r_idx]
                row1 += ["科目", it['科目'], "課本", it['課本'], ""]
                row2 += ["版本", it['版本'], "習作", it['習作'], ""]
                row3 += ["冊別", it['冊別'], "小計", it['小計'], ""]
            else:
                row1 += [""]*5; row2 += [""]*5; row3 += [""]*5
        csv_writer.writerow(row1); csv_writer.writerow(row2); csv_writer.writerow(row3); csv_writer.writerow([])
        
    st.download_button(
        label="💾 下載費用明細表 (CSV)",
        data=output_buffer.getvalue().encode('utf-8-sig'),
        file_name="教科書費用明細表.csv",
        mime="text/csv"
    )
