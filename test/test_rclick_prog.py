"""
程序化右键测试 — 模拟 <Button-3> 事件并检测响应
"""
import tkinter as tk
import customtkinter as ctk
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ctk.set_appearance_mode("light")

results = []

def test(name, widget, bind_to=None):
    """在 widget 上绑 <Button-3>，模拟点击并检测是否触发"""
    triggered = []
    def cb(e):
        triggered.append(True)
    target = bind_to or widget
    target.bind("<Button-3>", cb, add=True)
    # 模拟右键事件
    widget.event_generate("<Button-3>", x=5, y=5)
    # 处理事件队列
    widget.update_idletasks()
    widget.update()
    ok = len(triggered) > 0
    results.append((name, ok, type(widget).__name__, type(target).__name__))
    if ok:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}")
    return ok


# ===== 创建根窗口 =====
root = ctk.CTk()
root.withdraw()
f = ctk.CTkFrame(root)
f.pack()

print("========= 右键事件传播测试 =========\n")

# 1. CTkLabel 独立 + CTkLabel.bind
lbl1 = ctk.CTkLabel(f, text="Test1", fg_color="#f0fdf4")
lbl1.pack()
test("CTkLabel 独立 + bind(lbl1)", lbl1, lbl1)

# 2. CTkLabel 独立 + _label.bind
lbl2 = ctk.CTkLabel(f, text="Test2", fg_color="#f0fdf4")
lbl2.pack()
test("CTkLabel 独立 + _label.bind", lbl2, lbl2._label)

# 3. CTkLabel 独立 + _canvas.bind
lbl3 = ctk.CTkLabel(f, text="Test3", fg_color="#f0fdf4")
lbl3.pack()
test("CTkLabel 独立 + _canvas.bind", lbl3, lbl3._canvas)

# 4. tk.Frame + CTkLabel, bind 到 label
f4 = tk.Frame(f, bg="#f0fdf4")
f4.pack()
lbl4 = ctk.CTkLabel(f4, text="Test4", fg_color="#f0fdf4")
lbl4.pack()
test("tk.Frame + CTkLabel, bind(label)", lbl4, lbl4)

# 5. tk.Frame + CTkLabel, bind 到 frame
f5 = tk.Frame(f, bg="#f0fdf4")
f5.pack()
lbl5 = ctk.CTkLabel(f5, text="Test5", fg_color="#f0fdf4")
lbl5.pack()
test("tk.Frame + CTkLabel, bind(frame)", lbl5, f5)

# 6. 透明 CTkFrame + CTkLabel, bind(label)
f6 = ctk.CTkFrame(f, fg_color="transparent")
f6.pack()
lbl6 = ctk.CTkLabel(f6, text="Test6")
lbl6.pack()
test("透明 CTkFrame + CTkLabel, bind(label)", lbl6, lbl6)

# 7. 透明 CTkFrame + CTkLabel(fg_color=色), bind(label)
f7 = ctk.CTkFrame(f, fg_color="transparent")
f7.pack()
lbl7 = ctk.CTkLabel(f7, text="Test7", fg_color="#f0fdf4")
lbl7.pack()
test("透明CTkFrame + CTkLabel(fg=色), bind(label)", lbl7, lbl7)

# 8. CTkFrame(bg=色) + CTkLabel(fg=色), bind(label)
f8 = ctk.CTkFrame(f, fg_color="#f0fdf4")
f8.pack()
lbl8 = ctk.CTkLabel(f8, text="Test8", fg_color="#f0fdf4")
lbl8.pack()
test("CTkFrame(色) + CTkLabel(色), bind(label)", lbl8, lbl8)

# 9. CTkFrame(bg=色) + CTkLabel(fg=色), bind(frame)
f9 = ctk.CTkFrame(f, fg_color="#f0fdf4")
f9.pack()
lbl9 = ctk.CTkLabel(f9, text="Test9", fg_color="#f0fdf4")
lbl9.pack()
test("CTkFrame(色) + CTkLabel(色), bind(frame)", lbl9, f9)

# 10. tk.Label 独立
lbl10 = tk.Label(f, text="Test10", bg="#f0fdf4")
lbl10.pack()
test("tk.Label 独立", lbl10, lbl10)

# 11. tk.Frame + tk.Label, bind(label)
f11 = tk.Frame(f, bg="#f0fdf4")
f11.pack()
lbl11 = tk.Label(f11, text="Test11", bg="#f0fdf4")
lbl11.pack()
test("tk.Frame + tk.Label, bind(label)", lbl11, lbl11)

# 12. tk.Frame + tk.Label, bind(frame)
f12 = tk.Frame(f, bg="#f0fdf4")
f12.pack()
lbl12 = tk.Label(f12, text="Test12", bg="#f0fdf4")
lbl12.pack()
test("tk.Frame + tk.Label, bind(frame)", lbl12, f12)


print(f"\n========= 结果汇总 =========")
for name, ok, wtype, ttype in results:
    status = "✅" if ok else "❌"
    print(f"  {status} {name:45s}  widget={wtype:15s}  target={ttype:15s}")

root.destroy()
