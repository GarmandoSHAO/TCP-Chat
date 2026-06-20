"""
Windows API 模拟右键点击测试
使用 ctypes 调用 user32.dll 的 SendInput 来模拟真实鼠标右键
"""
import tkinter as tk
import customtkinter as ctk
import ctypes
import ctypes.wintypes
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ctk.set_appearance_mode("light")

# Windows API constants
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

# Structures for SendInput
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", _INPUT),
    ]

INVALID_HANDLE_VALUE = 0xFFFFFFFF
INPUT_MOUSE = 0


def sim_right_click(x, y):
    """使用 Windows SendInput 模拟右键点击"""
    # Move cursor
    ctypes.windll.user32.SetCursorPos(x, y)
    time.sleep(0.05)

    # right down
    mi_down = MOUSEINPUT(x, y, 0, MOUSEEVENTF_RIGHTDOWN, 0, None)
    inp_down = INPUT(INPUT_MOUSE, INPUT._INPUT(mi=mi_down))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
    time.sleep(0.05)

    # right up
    mi_up = MOUSEINPUT(x, y, 0, MOUSEEVENTF_RIGHTUP, 0, None)
    inp_up = INPUT(INPUT_MOUSE, INPUT._INPUT(mi=mi_up))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
    time.sleep(0.05)


# ========== 测试窗口 ==========
root = ctk.CTk()
root.geometry("500x400+200+200")
root.title("右键自动测试")
root.update()

# 模拟 app.py 结构
canvas = tk.Canvas(root, bd=0, highlightthickness=0, bg="#ffffff")
canvas.pack(fill="both", expand=True, padx=10, pady=10)
user_list_inner = ctk.CTkFrame(canvas, fg_color="transparent")
canvas.create_window((0, 0), window=user_list_inner, anchor="nw", tags="inner")

results = []

def rclick_hit(name):
    results.append(name)
    print(f"  ✅ {name}")

fs = 12
widgets_to_test = []

test_configs = [
    # (label, fg_color for label, desc)
]

for i, nick in enumerate(["Alice", "Bob", "Carol"]):
    bg = "#f0fdf4"
    hover_bg = "#c8f0d0"

    row = ctk.CTkFrame(user_list_inner, fg_color="transparent")
    row.pack(fill="x", pady=1, padx=4)

    indicator = "  ● "
    ctk.CTkLabel(
        row, text=indicator, font=("Segoe UI", fs + 2),
        text_color="#4caf50", fg_color="transparent",
    ).pack(side="left", padx=(6, 2))

    # 测试不同方案
    if i == 0:
        # 方案 A：CTkLabel + fg_color=色 + bind(lbl) ← 当前 app.py
        lbl = ctk.CTkLabel(
            row, text=nick, font=("Segoe UI", fs),
            anchor="w", fg_color=bg, cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True)
        lbl.bind("<Button-3>", lambda e, n=nick: rclick_hit(f"A_{n}"))
        widgets_to_test.append(("A-CTkLabel绑定", lbl, nick))

    elif i == 1:
        # 方案 B：CTkLabel + fg_color=色 + _label.bind
        lbl = ctk.CTkLabel(
            row, text=nick, font=("Segoe UI", fs),
            anchor="w", fg_color=bg, cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True)
        lbl._label.bind("<Button-3>", lambda e, n=nick: rclick_hit(f"B_{n}"))
        widgets_to_test.append(("B-_label绑定", lbl._label, nick))

    elif i == 2:
        # 方案 C：CTkLabel + fg_color=透 + bind(lbl) + _label.bind 雙重
        lbl = ctk.CTkLabel(
            row, text=nick, font=("Segoe UI", fs),
            anchor="w", fg_color="transparent", cursor="hand2",
        )
        lbl.pack(side="left", fill="x", expand=True)
        lbl.bind("<Button-3>", lambda e, n=nick: rclick_hit(f"C1_{n}"))
        lbl._label.bind("<Button-3>", lambda e, n=nick: rclick_hit(f"C2_{n}"))
        widgets_to_test.append(("C-透明_label", lbl._label, nick))
        widgets_to_test.append(("C-透明_CTkLabel", lbl, nick))


root.update()
canvas.configure(scrollregion=canvas.bbox("all"))
canvas.itemconfig("inner", width=canvas.winfo_width())

# 等待窗口完全显示
time.sleep(0.5)

# 获取每个 widget 的屏幕坐标并模拟右键
print("\\n===== 开始自动右键测试 =====\\n")

for desc, widget, nick in widgets_to_test:
    try:
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() // 2
        print(f"  点击 {desc} ({nick}) at ({x}, {y})")
        sim_right_click(x, y)
    except Exception as e:
        print(f"  ❌ 点击 {desc} 失败: {e}")

time.sleep(0.3)

print(f"\\n===== 测试结果 =====")
for name in ["A_Alice", "B_Bob", "C1_Carol", "C2_Carol"]:
    if name in results:
        print(f"  ✅ {name} 触发成功")
    else:
        print(f"  ❌ {name} 未触发")

root.destroy()
print("\\n测试完成")
