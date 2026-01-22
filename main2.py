import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pdfplumber
import re
import csv
from collections import defaultdict


class SortedSubjectTextbookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("教科書費用查詢")
        self.root.geometry("800x500")

        # 1. 資料與變數
        self.db = {}
        self.selected_grade = tk.StringVar()
        self.selected_subject = tk.StringVar()
        self.selected_volume = tk.StringVar()
        self.selected_version = tk.StringVar()

        # 定義排序優先權
        self.sort_order = ["國語", "國文", "數學", "生活", "社會", "自然", "藝術", "健體", "健康", "綜合", "英語", "英文"]

        self.versions = []
        self.create_widgets()

    def create_widgets(self):
        # --- 頂部：檔案選取 ---
        top_bar = tk.Frame(self.root, bg="#eeeeee", pady=3)
        top_bar.pack(fill="x")
        tk.Button(top_bar, text="📁 載入 PDF", command=self.load_pdf, font=("微軟正黑體", 9)).pack(side="left", padx=10)
        self.file_label = tk.Label(top_bar, text="請載入 PDF 價格表", fg="gray", bg="#eeeeee", font=("微軟正黑體", 9))
        self.file_label.pack(side="left")

        # --- 主區域 ---
        main_content = tk.Frame(self.root, pady=5)
        main_content.pack(fill="both", expand=True)

        left_frame = tk.Frame(main_content, width=380)
        left_frame.pack(side="left", padx=10, fill="y")

        # 1. 年級
        f_grade = tk.LabelFrame(left_frame, text="1. 年級", font=("微軟正黑體", 9))
        f_grade.pack(fill="x", pady=2)
        for i, g in enumerate(["1", "2", "3", "4", "5", "6"]):
            tk.Radiobutton(f_grade, text=f"{g}年", variable=self.selected_grade, value=g,
                           command=self.refresh_subjects, indicatoron=0, width=4, font=("微軟正黑體", 9),
                           selectcolor="#ADD8E6").grid(row=0, column=i, padx=1)

        # 2. 科目
        self.f_subject = tk.LabelFrame(left_frame, text="2. 選取科目", font=("微軟正黑體", 9))
        self.f_subject.pack(fill="x", pady=2)
        self.sub_container = tk.Frame(self.f_subject)
        self.sub_container.pack(pady=2)

        # 3. 冊別
        self.f_volume = tk.LabelFrame(left_frame, text="3. 選取冊別", font=("微軟正黑體", 9))
        self.f_volume.pack(fill="x", pady=2)
        self.vol_container = tk.Frame(self.f_volume)
        self.vol_container.pack(pady=2)

        # 4. 版本
        self.f_version = tk.LabelFrame(left_frame, text="4. 選取版本", font=("微軟正黑體", 9))
        self.f_version.pack(fill="x", pady=2)
        self.ver_btn_container = tk.Frame(self.f_version)
        self.ver_btn_container.pack(pady=2)

        tk.Button(left_frame, text="➕ 加入查詢清單", font=("微軟正黑體", 10, "bold"),
                  command=self.add_to_list, bg="#0078D7", fg="white", pady=5).pack(fill="x", pady=10)

        # --- 右側：表格 ---
        right_frame = tk.Frame(main_content)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)

        cols = ("g", "s", "v", "vol", "pb", "pw", "total")
        self.tree = ttk.Treeview(right_frame, columns=cols, show="headings", height=18)
        headings = {"g": "年級", "s": "科目", "v": "版本", "vol": "冊", "pb": "課本", "pw": "習作", "total": "合計"}
        for col, text in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=70, anchor="center")
        self.tree.pack(fill="both", expand=True)

        btn_bar = tk.Frame(right_frame)
        btn_bar.pack(fill="x", pady=5)
        # 這裡就是發生錯誤的地方，現在已經補上 clear_all 函式
        tk.Button(btn_bar, text="🗑️ 移除選取", command=self.remove_item, font=("微軟正黑體", 9)).pack(side="left",
                                                                                                      padx=2)
        tk.Button(btn_bar, text="🔄 全部清空", command=self.clear_all, font=("微軟正黑體", 9)).pack(side="left", padx=2)
        tk.Button(btn_bar, text="📊 匯出統計報表", command=self.export_spaced_blocks_csv,
                  font=("微軟正黑體", 9, "bold"), bg="#27AE60", fg="white").pack(side="right", padx=5)

    def get_subject_weight(self, sub_name):
        for i, keyword in enumerate(self.sort_order):
            if keyword in sub_name: return i
        return 999

    def extract_price(self, t):
        if not t or "-" in str(t): return 0
        m = re.search(r'\d+', str(t).replace('\n', '').replace(',', ''))
        return int(m.group()) if m else 0

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not file_path: return
        try:
            new_db = {}
            detected_vers = []
            valid_found = False
            target_names = ["南一", "康軒", "翰林", "育成", "佳音", "何嘉仁", "吉的堡", "台灣培生", "全華", "龍騰", "泰宇", "三民"]

            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table[0]) < 4: continue
                        if not detected_vers:
                            for r_idx in range(min(10, len(table))):
                                row = table[r_idx]
                                for i, cell in enumerate(row):
                                    txt = str(cell or "").replace("\n", "").strip()
                                    for k in target_names:
                                        if k in txt:
                                            detected_vers.append((k, i))
                                            break
                                if detected_vers: break
                        for row in table:
                            row_str = "".join([str(c) for c in row if c])
                            if "課本" in row_str or "習作" in row_str:
                                if row[1] and row[2]:
                                    valid_found = True
                                    raw_s = str(row[1]).strip()
                                    s_name = re.sub(r'^\d+\s*|\s*\d+$', '', raw_s)
                                    key = (str(row[2]).strip(), s_name, str(row[3]).strip())
                                    cat = "課" if "課本" in row_str else "習"
                                    price_dict = {}
                                    for v_name, col_idx in detected_vers:
                                        if col_idx < len(row):
                                            price_dict[v_name] = self.extract_price(row[col_idx])
                                    if key not in new_db: new_db[key] = {}
                                    if cat not in new_db[key]:
                                        new_db[key][cat] = price_dict
                                    else:
                                        new_db[key][cat].update(price_dict)
            if not valid_found:
                messagebox.showerror("格式不符", "⚠️ 無法解析此 PDF。")
                return
            self.db = new_db
            self.versions = [v[0] for v in detected_vers]
            self.refresh_version_ui()
            self.file_label.config(text=f"✅ 已讀取：{file_path.split('/')[-1]}", fg="#2ECC71")
            self.refresh_subjects()
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取失敗：{e}")

    def refresh_version_ui(self):
        for w in self.ver_btn_container.winfo_children(): w.destroy()
        for i, v in enumerate(self.versions):
            tk.Radiobutton(self.ver_btn_container, text=v, variable=self.selected_version, value=v,
                           indicatoron=0, width=8, font=("微軟正黑體", 9), selectcolor="#90EE90").grid(row=i // 4,
                                                                                                       column=i % 4,
                                                                                                       padx=1, pady=2)
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
                           selectcolor="#FFD700").grid(row=i // 3, column=i % 3, padx=1, pady=1)

    def refresh_volumes(self):
        for w in self.vol_container.winfo_children(): w.destroy()
        g, s_name = self.selected_grade.get(), self.selected_subject.get()
        v_list = sorted(list(set([k[2] for k in self.db.keys() if k[0] == g and k[1] == s_name])))
        for i, v in enumerate(v_list):
            tk.Radiobutton(self.vol_container, text=v, variable=self.selected_volume, value=v,
                           indicatoron=0, width=6, font=("微軟正黑體", 9), selectcolor="#FFB6C1").grid(row=i // 4,
                                                                                                       column=i % 4,
                                                                                                       padx=1, pady=1)

    def add_to_list(self):
        g, s_name, vol, ver = self.selected_grade.get(), self.selected_subject.get(), self.selected_volume.get(), self.selected_version.get()
        if not all([g, s_name, vol, ver]): return
        res = self.db.get((g, s_name, vol), {})
        pb = res.get("課", {}).get(ver, 0)
        pw = res.get("習", {}).get(ver, 0)
        self.tree.insert("", "end", values=(f"{g}年", s_name, ver, vol, pb, pw, pb + pw))

    def remove_item(self):
        for item in self.tree.selection(): self.tree.delete(item)

    # --- 修正處：補回清空功能 ---
    def clear_all(self):
        """清空查詢清單中的所有項目"""
        if messagebox.askyesno("確認", "是否要清空清單中的所有內容？"):
            for item in self.tree.get_children():
                self.tree.delete(item)

    # --- 橫向呈現總計摘要匯出邏輯 ---
    def export_spaced_blocks_csv(self):
        items = self.tree.get_children()
        if not items: return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")],
                                                 initialfile="教科書費用統計表.csv")
        if not file_path: return

        grade_groups = defaultdict(list)
        grade_totals = defaultdict(int)
        ver_totals = defaultdict(int)
        grand_total = 0

        for item in items:
            val = self.tree.item(item)['values']
            grade_groups[val[0]].append(val)
            price = int(val[6])
            grade_totals[val[0]] += price
            ver_totals[val[2]] += price
            grand_total += price

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                writer.writerow(["【費用總計摘要】"])

                # 1. 各年級橫向
                g_keys = sorted(grade_totals.keys(),
                                key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
                writer.writerow(["各年級項目"] + [f"{g}總計" for g in g_keys] + ["全校總預算"])
                writer.writerow(["金額 (元)"] + [grade_totals[g] for g in g_keys] + [grand_total])

                writer.writerow([])

                # 2. 各廠商橫向
                v_keys = sorted(ver_totals.keys())
                writer.writerow(["各廠商項目"] + [f"{v}總計" for v in v_keys])
                writer.writerow(["金額 (元)"] + [ver_totals[v] for v in v_keys])

                writer.writerow([])
                writer.writerow([])

                writer.writerow(["【詳細清單明細】"])
                sorted_grades = sorted(grade_groups.keys(),
                                       key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)

                h_row = []
                for i, g in enumerate(sorted_grades):
                    h_row += [g, "", "", ""]
                    if i < len(sorted_grades) - 1: h_row += [""]
                writer.writerow(h_row)

                max_b = max(len(grade_groups[g]) for g in sorted_grades)
                for b_idx in range(max_b):
                    r1, r2, r3 = [], [], []
                    for i, g in enumerate(sorted_grades):
                        books = grade_groups[g]
                        if b_idx < len(books):
                            b = books[b_idx]
                            r1 += ["科目", b[1], "課本價格", b[4]]
                            r2 += ["版本", b[2], "習作價格", b[5]]
                            r3 += ["冊別", b[3], "總計金額", b[6]]
                        else:
                            r1 += ["", "", "", ""];
                            r2 += ["", "", "", ""];
                            r3 += ["", "", "", ""]
                        if i < len(sorted_grades) - 1: r1 += [""]; r2 += [""]; r3 += [""]
                    writer.writerow(r1);
                    writer.writerow(r2);
                    writer.writerow(r3)
                    writer.writerow([])

            messagebox.showinfo("成功", f"報表已成功匯出至：\n{file_path}")
        except Exception as e:
            messagebox.showerror("錯誤", f"匯出失敗: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = SortedSubjectTextbookApp(root)
    root.mainloop()