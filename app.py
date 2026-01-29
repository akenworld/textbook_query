import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pdfplumber
import re
import csv
import io
from collections import defaultdict

class TextbookSystemApp:
    def __init__(self, root):
        self.root = root
        self.root.title("進階教科書價格查詢系統")
        self.root.geometry("1100x650")
        self.root.configure(bg="#f0f0f0")

        # 1. 資料與變數
        self.db = {}
        self.selected_grade = tk.StringVar()
        self.selected_subject = tk.StringVar()
        self.selected_volume = tk.StringVar()
        self.selected_version = tk.StringVar()

        self.sort_order = ["國語", "國文", "數學", "生活", "社會", "自然", "藝術", "健體", "健康", "綜合", "英語", "英文"]
        self.target_publishers = ["南一", "康軒", "翰林", "育成", "佳音", "何嘉仁", "吉的堡", "台灣培生", "全華", "龍騰", "泰宇", "三民"]
        self.versions = []

        self.create_widgets()

    def create_widgets(self):
        # --- 頂部導航 ---
        top_bar = tk.Frame(self.root, bg="#2c3e50", pady=10)
        top_bar.pack(fill="x")

        tk.Button(top_bar, text="📁 1. 載入價格 PDF", command=self.load_pdf,
                  bg="#3498db", fg="white", font=("微軟正黑體", 10, "bold")).pack(side="left", padx=10)
        
        tk.Button(top_bar, text="🟢 2. 匯入選用一覽表", command=self.import_version_table,
                  bg="#27ae60", fg="white", font=("微軟正黑體", 10, "bold")).pack(side="left", padx=10)

        tk.Button(top_bar, text="📥 下載範例檔", command=self.download_template,
                  bg="#5D6D7E", fg="white", font=("微軟正黑體", 10)).pack(side="left", padx=10)

        self.file_label = tk.Label(top_bar, text="請先載入 PDF 再操作匯入", fg="#ecf0f1", bg="#2c3e50", font=("微軟正黑體", 10))
        self.file_label.pack(side="left", padx=10)

        # --- 主內容區域 ---
        pw = tk.PanedWindow(self.root, orient="horizontal", bg="#f0f0f0", sashwidth=4)
        pw.pack(fill="both", expand=True, padx=5, pady=5)

        left_frame = tk.Frame(pw)
        pw.add(left_frame, width=380)

        f_grade = tk.LabelFrame(left_frame, text="1. 手動選擇年級", font=("微軟正黑體", 10, "bold"))
        f_grade.pack(fill="x", pady=5)
        for i, g in enumerate(["1", "2", "3", "4", "5", "6"]):
            tk.Radiobutton(f_grade, text=f"{g}年", variable=self.selected_grade, value=g,
                           command=self.refresh_subjects, indicatoron=0, width=5,
                           selectcolor="#AED6F1", font=("微軟正黑體", 9)).grid(row=0, column=i, padx=2, pady=5)

        self.f_sub = tk.LabelFrame(left_frame, text="2. 手動選擇科目", font=("微軟正黑體", 10, "bold"))
        self.f_sub.pack(fill="both", expand=True, pady=5)
        self.sub_canvas = tk.Canvas(self.f_sub, height=100)
        self.sub_scrollbar = ttk.Scrollbar(self.f_sub, orient="vertical", command=self.sub_canvas.yview)
        self.sub_container = tk.Frame(self.sub_canvas)
        self.sub_container.bind("<Configure>", lambda e: self.sub_canvas.configure(scrollregion=self.sub_canvas.bbox("all")))
        self.sub_canvas.create_window((0, 0), window=self.sub_container, anchor="nw")
        self.sub_canvas.configure(yscrollcommand=self.sub_scrollbar.set)
        self.sub_canvas.pack(side="left", fill="both", expand=True)
        self.sub_scrollbar.pack(side="right", fill="y")

        self.f_vol = tk.LabelFrame(left_frame, text="3. 選擇冊別", font=("微軟正黑體", 10, "bold"))
        self.f_vol.pack(fill="x", pady=5)
        self.vol_container = tk.Frame(self.f_vol)
        self.vol_container.pack(pady=5)

        self.f_ver = tk.LabelFrame(left_frame, text="4. 選擇版本", font=("微軟正黑體", 10, "bold"))
        self.f_ver.pack(fill="x", pady=5)
        self.ver_btn_container = tk.Frame(self.f_ver)
        self.ver_btn_container.pack(pady=5)

        tk.Button(left_frame, text="➕ 加入查詢清單", command=self.add_to_list,
                  bg="#3498db", fg="white", font=("微軟正黑體", 11, "bold"), pady=8).pack(fill="x", pady=10)

        right_frame = tk.Frame(pw)
        pw.add(right_frame)

        cols = ("g", "s", "v", "vol", "pb", "pw", "total")
        self.tree = ttk.Treeview(right_frame, columns=cols, show="headings")
        headings = {"g": "年級", "s": "科目", "v": "版本", "vol": "冊別", "pb": "課本", "pw": "習作", "total": "小計"}
        for col, text in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=65, anchor="center")
        self.tree.pack(fill="both", expand=True)

        btn_bar = tk.Frame(right_frame, pady=5)
        btn_bar.pack(fill="x")
        tk.Button(btn_bar, text="🗑️ 移除選取", command=self.remove_item).pack(side="left", padx=5)
        tk.Button(btn_bar, text="🔄 全部清空", command=self.clear_all).pack(side="left", padx=5)
        tk.Button(btn_bar, text="📊 匯出報表 (總計在最上)", command=self.export_csv,
                  bg="#8e44ad", fg="white", font=("微軟正黑體", 10, "bold")).pack(side="right", padx=5)

    def download_template(self):
        template_content = (
            "教科書一覽表,,,,,,\n"
            "科目/年級,一年級,二年級,三年級,四年級,五年級,六年級\n"
            "國語,康軒,康軒,南一,康軒,南一,康軒\n"
            "數學,南一,南一,南一,南一,翰林,南一\n"
            "生活,翰林,翰林,,,,\n"
            "健康與體育,翰林,翰林,南一,康軒,南一,南一\n"
            "自然科學,,,南一,翰林,南一,翰林\n"
            "社會,,,康軒,康軒,南一,翰林\n"
            "英語,,,康軒,翰林,翰林,何嘉仁\n"
            "綜合活動,,,翰林,康軒,康軒,南一\n"
            "藝術,,,康軒,翰林,康軒,康軒\n"
        )
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], initialfile="教科書版本一覽表(範例檔).csv")
        if file_path:
            try:
                with open(file_path, mode='w', encoding='utf-8-sig', newline='') as f: f.write(template_content)
                messagebox.showinfo("成功", "範例檔已儲存。")
            except Exception as e: messagebox.showerror("錯誤", f"儲存失敗：{e}")

    def import_version_table(self):
        if not self.db:
            messagebox.showwarning("提醒", "請先載入 PDF 價格表！")
            return
        file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path: return
        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f: reader = list(csv.reader(f))
            if len(reader) < 2: return
            grade_row = reader[1]
            grade_map = {}
            for idx, cell in enumerate(grade_row):
                m = re.search(r'([一二三四五六])', cell)
                if m: grade_map[m.group(1)] = idx
            
            items_added = 0
            for row in reader[2:]:
                if not row or not row[0]: continue
                subject = row[0].strip()
                for g_zh, col_idx in grade_map.items():
                    if col_idx >= len(row): continue
                    version = row[col_idx].strip()
                    if not version: continue
                    g_num = {"一":"1", "二":"2", "三":"3", "四":"4", "五":"5", "六":"6"}[g_zh]
                    vols = sorted(list(set([k[2] for k in self.db.keys() if k[0] == g_num and k[1] == subject])))
                    if vols:
                        target_vol = ""
                        for v in vols:
                            if str(int(g_num)*2) in v: target_vol = v; break
                        if not target_vol: target_vol = vols[0]
                        res = self.db.get((g_num, subject, target_vol), {})
                        pb = res.get("課", {}).get(version, 0)
                        pw = res.get("習", {}).get(version, 0)
                        if pb > 0 or pw > 0:
                            self.tree.insert("", "end", values=(f"{g_num}年", subject, version, target_vol, pb, pw, pb + pw))
                            items_added += 1
            messagebox.showinfo("完成", f"匯入成功！已帶入 {items_added} 筆。")
        except Exception as e: messagebox.showerror("錯誤", f"匯入失敗：{e}")

    # --- 關鍵修正：輸出報表總計在最上方 ---
    def export_csv(self):
        items = self.tree.get_children()
        if not items: return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="教科書費用明細表.csv")
        if not file_path: return
        
        grade_groups = defaultdict(list)
        grade_totals = defaultdict(int)
        for item in items:
            val = self.tree.item(item)['values']
            grade_groups[val[0]].append(val)
            grade_totals[val[0]] += int(val[6]) # 累加總計

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                sorted_grades = sorted(grade_groups.keys())
                
                # A. 第一行：大標題
                h_row = []
                for g in sorted_grades: h_row += [f"【{g}】", "", "", "", ""]
                writer.writerow(h_row)

                # B. 第二行：總計列 (修正點：移到最上面)
                total_row = []
                for g in sorted_grades:
                    total_row += ["★年級總計", "", "", grade_totals[g], ""]
                writer.writerow(total_row)
                writer.writerow([]) # 空行隔開

                # C. 後續：詳細清單
                max_b = max(len(grade_groups[g]) for g in sorted_grades)
                for b_idx in range(max_b):
                    r1, r2, r3 = [], [], []
                    for g in sorted_grades:
                        books = grade_groups[g]
                        if b_idx < len(books):
                            b = books[b_idx]
                            r1 += ["科目", b[1], "課本", b[4], ""]
                            r2 += ["版本", b[2], "習作", b[5], ""]
                            r3 += ["冊別", b[3], "小計", b[6], ""]
                        else:
                            r1 += ["", "", "", "", ""]; r2 += ["", "", "", "", ""]; r3 += ["", "", "", "", ""]
                    writer.writerow(r1); writer.writerow(r2); writer.writerow(r3); writer.writerow([])

            messagebox.showinfo("成功", f"報表已匯出，總計已置頂。\n路徑：{file_path}")
        except Exception as e: messagebox.showerror("錯誤", f"匯出失敗: {e}")

    # (其餘 load_pdf, extract_price 等基礎函數維持不變)
    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not file_path: return
        try:
            new_db = {}
            detected_vers = []
            col_map = {"年級": 2, "科目": 1, "冊別": 3}
            valid_found = False
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table[0]) < 4: continue
                        for r_idx in range(min(10, len(table))):
                            row = table[r_idx]
                            for i, cell in enumerate(row):
                                txt = str(cell or "").replace("\n", "").strip()
                                for k in self.target_publishers:
                                    if k in txt and (k, i) not in detected_vers:
                                        detected_vers.append((k, i))
                                if "年級" in txt: col_map["年級"] = i
                                if "科目" in txt: col_map["科目"] = i
                                if "冊" in txt: col_map["冊別"] = i
                        for row in table:
                            row_str = "".join([str(c) for c in row if c])
                            if "課本" in row_str or "習作" in row_str:
                                if row[col_map["科目"]] and row[col_map["年級"]]:
                                    valid_found = True
                                    raw_s = str(row[col_map["科目"]]).strip()
                                    s_name = re.sub(r'^\d+\s*|\s*\d+$', '', raw_s)
                                    g_name = str(row[col_map["年級"]]).strip()
                                    v_name = str(row[col_map["冊別"]]).strip()
                                    key = (g_name, s_name, v_name)
                                    cat = "課" if "課本" in row_str else "習"
                                    price_dict = {}
                                    for ver_name, col_idx in detected_vers:
                                        if col_idx < len(row):
                                            price_dict[ver_name] = self.extract_price(row[col_idx])
                                    if key not in new_db: new_db[key] = {"課": {}, "習": {}}
                                    new_db[key][cat].update(price_dict)
            self.db = new_db
            self.versions = [v[0] for v in sorted(detected_vers, key=lambda x: x[1])]
            self.refresh_version_ui()
            self.file_label.config(text=f"✅ 已載入價格 PDF", fg="#2ecc71")
            self.refresh_subjects()
            messagebox.showinfo("完成", "載入成功！")
        except Exception as e: messagebox.showerror("錯誤", f"讀取失敗：{e}")

    def extract_price(self, t):
        if not t or "-" in str(t): return 0
        m = re.search(r'\d+', str(t).replace('\n', '').replace(',', ''))
        return int(m.group()) if m else 0

    def refresh_version_ui(self):
        for w in self.ver_btn_container.winfo_children(): w.destroy()
        for i, v in enumerate(self.versions):
            tk.Radiobutton(self.ver_btn_container, text=v, variable=self.selected_version, value=v,
                           indicatoron=0, width=8, font=("微軟正黑體", 9), selectcolor="#90EE90").grid(row=i // 4, column=i % 4, padx=2, pady=2)
        if self.versions: self.selected_version.set(self.versions[0])

    def refresh_subjects(self):
        for w in self.sub_container.winfo_children(): w.destroy()
        grade = self.selected_grade.get()
        if not self.db: return
        raw_subjects = list(set([k[1] for k in self.db.keys() if k[0] == grade]))
        sorted_subjects = sorted(raw_subjects, key=lambda x: (self.get_subject_weight(x), x))
        for i, s_name in enumerate(sorted_subjects):
            tk.Radiobutton(self.sub_container, text=s_name, variable=self.selected_subject, value=s_name,
                           command=self.refresh_volumes, indicatoron=0, width=12, font=("微軟正黑體", 9),
                           selectcolor="#FFD700").grid(row=i // 3, column=i % 3, padx=2, pady=2)

    def refresh_volumes(self):
        for w in self.vol_container.winfo_children(): w.destroy()
        g, s_name = self.selected_grade.get(), self.selected_subject.get()
        v_list = sorted(list(set([k[2] for k in self.db.keys() if k[0] == g and k[1] == s_name])))
        for i, v in enumerate(v_list):
            tk.Radiobutton(self.vol_container, text=v, variable=self.selected_volume, value=v,
                           indicatoron=0, width=6, font=("微軟正黑體", 9), selectcolor="#FFB6C1").grid(row=0, column=i, padx=2, pady=2)

    def add_to_list(self):
        g, s, vol, ver = self.selected_grade.get(), self.selected_subject.get(), self.selected_volume.get(), self.selected_version.get()
        if not all([g, s, vol, ver]):
            messagebox.showwarning("提示", "請選齊欄位！")
            return
        res = self.db.get((g, s, vol), {})
        pb = res.get("課", {}).get(ver, 0)
        pw = res.get("習", {}).get(ver, 0)
        self.tree.insert("", "end", values=(f"{g}年", s, ver, vol, pb, pw, pb + pw))

    def remove_item(self):
        for item in self.tree.selection(): self.tree.delete(item)

    def clear_all(self):
        if messagebox.askyesno("清空", "確定要清空嗎？"):
            for item in self.tree.get_children(): self.tree.delete(item)

    def get_subject_weight(self, sub_name):
        for i, keyword in enumerate(self.sort_order):
            if keyword in sub_name: return i
        return 999

if __name__ == "__main__":
    root = tk.Tk()
    app = TextbookSystemApp(root)
    root.mainloop()
