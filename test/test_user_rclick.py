"""
用户列表右键调试脚本
测试各种 widget 组合下 <Button-3> 是否正常触发
"""
import tkinter as tk
import customtkinter as ctk

ctk.set_appearance_mode("light")


class TestWindow(ctk.CTkToplevel):
    """独立测试窗口，模拟用户列表的场景"""

    def __init__(self):
        super().__init__(None)
        self.title("右键调试")
        self.geometry("400x500+200+200")

        self._log("======== 右键绑定测试 ========")
        self._log("右键点击每个标签，查看是否有回调输出\n")

        # ---------- 测试 A：原始模式（透明 CTkFrame + CTkLabel）----------
        self._section("A) 原始：透明 CTkFrame + CTkLabel（无 fg_color）")
        fA = ctk.CTkFrame(self, fg_color="transparent")
        fA.pack(fill="x", pady=2, padx=10)
        lblA = ctk.CTkLabel(fA, text="  ●  Alice", anchor="w", font=("Segoe UI", 12))
        lblA.pack(side="left", fill="x", expand=True)
        lblA.bind("<Button-3>", lambda e: self._rclick("A 命中"))
        lblA.bind("<Enter>", lambda e: self._log("  A <Enter>"))
        lblA.bind("<Leave>", lambda e: self._log("  A <Leave>"))

        # ---------- 测试 B：CTkLabel 加 fg_color=bg ----------
        self._section("B) CTkLabel + fg_color=#f0fdf4 (实色背景)")
        fB = ctk.CTkFrame(self, fg_color="transparent")
        fB.pack(fill="x", pady=2, padx=10)
        lblB = ctk.CTkLabel(
            fB, text="  ●  Bob", anchor="w", font=("Segoe UI", 12),
            fg_color="#f0fdf4",
        )
        lblB.pack(side="left", fill="x", expand=True)
        lblB.bind("<Button-3>", lambda e: self._rclick("B 命中"))
        lblB.bind("<Enter>", lambda e: self._log("  B <Enter>"))
        lblB.bind("<Leave>", lambda e: self._log("  B <Leave>"))

        # ---------- 测试 C：tk.Frame + CTkLabel ----------
        self._section("C) tk.Frame(bg=色) + CTkLabel(transparent)")
        fC = tk.Frame(self, bg="#f0fdf4", height=28, highlightthickness=0)
        fC.pack(fill="x", pady=2, padx=10)
        fC.pack_propagate(False)
        lblC = ctk.CTkLabel(
            fC, text="  ●  Carol", anchor="w", font=("Segoe UI", 12),
            fg_color="transparent",
        )
        lblC.pack(side="left", fill="x", expand=True)
        fC.bind("<Button-3>", lambda e: self._rclick("C frame 命中"))
        lblC.bind("<Button-3>", lambda e: self._rclick("C label 命中"))
        fC.bind("<Enter>", lambda e: self._log("  C frame <Enter>"))
        fC.bind("<Leave>", lambda e: self._log("  C frame <Leave>"))
        lblC.bind("<Enter>", lambda e: self._log("  C label <Enter>"))
        lblC.bind("<Leave>", lambda e: self._log("  C label <Leave>"))

        # ---------- 测试 D：tk.Frame + tk.Label ----------
        self._section("D) tk.Frame(bg=色) + tk.Label(bg=色)")
        fD = tk.Frame(self, bg="#f0fdf4", height=28, highlightthickness=0)
        fD.pack(fill="x", pady=2, padx=10)
        fD.pack_propagate(False)
        lblD = tk.Label(
            fD, text="  ●  Dave", font=("Segoe UI", 12),
            bg="#f0fdf4", anchor="w",
        )
        lblD.pack(side="left", fill="x", expand=True)
        fD.bind("<Button-3>", lambda e: self._rclick("D frame 命中"))
        lblD.bind("<Button-3>", lambda e: self._rclick("D label 命中"))
        fD.bind("<Enter>", lambda e: self._log("  D frame <Enter>"))
        fD.bind("<Leave>", lambda e: self._log("  D frame <Leave>"))
        lblD.bind("<Enter>", lambda e: self._log("  D label <Enter>"))
        lblD.bind("<Leave>", lambda e: self._log("  D label <Leave>"))

        # ---------- 测试 E：CTkFrame(bg=色) + CTkLabel(fg_color=色) ----------
        self._section("E) CTkFrame(bg) + CTkLabel(fg_color=色)")
        fE = ctk.CTkFrame(self, fg_color="#f0fdf4", height=28, corner_radius=6)
        fE.pack(fill="x", pady=2, padx=10)
        fE.pack_propagate(False)
        lblE = ctk.CTkLabel(
            fE, text="  ●  Eve", anchor="w", font=("Segoe UI", 12),
            fg_color="#f0fdf4",
        )
        lblE.pack(side="left", fill="x", expand=True)
        fE.bind("<Button-3>", lambda e: self._rclick("E frame 命中"))
        lblE.bind("<Button-3>", lambda e: self._rclick("E label 命中"))
        fE.bind("<Enter>", lambda e: self._log("  E frame <Enter>"))
        fE.bind("<Leave>", lambda e: self._log("  E frame <Leave>"))
        lblE.bind("<Enter>", lambda e: self._log("  E label <Enter>"))
        lblE.bind("<Leave>", lambda e: self._log("  E label <Leave>"))

        # ---------- 测试 F：直接 CTkLabel（无容器） ----------
        self._section("F) CTkLabel 独立（无容器，fg_color=色）")
        lblF = ctk.CTkLabel(
            self, text="  ●  Frank", anchor="w", font=("Segoe UI", 12),
            fg_color="#f0fdf4", corner_radius=6,
        )
        lblF.pack(fill="x", pady=2, padx=10)
        lblF.bind("<Button-3>", lambda e: self._rclick("F 命中"))
        lblF.bind("<Enter>", lambda e: self._log("  F <Enter>"))
        lblF.bind("<Leave>", lambda e: self._log("  F <Leave>"))

        # ---------- 测试 G：tk.Frame + 事件绑 _label 内部控件 ----------
        self._section("G) tk.Frame + lbl._label.bind")
        fG = tk.Frame(self, bg="#f0fdf4", height=28, highlightthickness=0)
        fG.pack(fill="x", pady=2, padx=10)
        fG.pack_propagate(False)
        lblG = ctk.CTkLabel(
            fG, text="  ●  Grace", anchor="w", font=("Segoe UI", 12),
            fg_color="#f0fdf4",
        )
        lblG.pack(side="left", fill="x", expand=True)
        # 直接绑 _label（tkinter.Label）
        lblG._label.bind("<Button-3>", lambda e: self._rclick("G _label 命中"))
        lblG._label.bind("<Enter>", lambda e: self._log("  G _label <Enter>"))
        lblG._label.bind("<Leave>", lambda e: self._log("  G _label <Leave>"))
        lblG._canvas.bind("<Button-3>", lambda e: self._rclick("G _canvas 命中"))

        # ---------- 测试 H：纯 tk.Label ----------
        self._section("H) 纯 tk.Label")
        lblH = tk.Label(
            self, text="  ●  Heidi", font=("Segoe UI", 12),
            bg="#f0fdf4", anchor="w", cursor="hand2",
        )
        lblH.pack(fill="x", pady=2, padx=10)
        lblH.bind("<Button-3>", lambda e: self._rclick("H 命中"))
        lblH.bind("<Enter>", lambda e: self._log("  H <Enter>"))
        lblH.bind("<Leave>", lambda e: self._log("  H <Leave>"))

    # ---- helpers ----
    _test_id = 0
    def _section(self, title):
        self._test_id += 1
        tk.Label(
            self, text=f"── {self._test_id}. {title} ──",
            font=("Segoe UI", 9, "bold"), fg="#666",
        ).pack(fill="x", pady=(10, 2), padx=10)

    def _rclick(self, msg):
        self._log(f"  >>> ✅ {msg}")

    def _log(self, msg):
        print(msg)


if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    w = TestWindow()
    w.focus()
    root.mainloop()
