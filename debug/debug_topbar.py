"""
Isolated login top bar debug - run this standalone
"""
import tkinter as tk
import customtkinter as ctk
import ctypes
import time

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

root = ctk.CTk()
root.title("DebugLogin")
root.geometry("420x480")
root.update()

# === Build EXACTLY like the login view ===
login_frame = ctk.CTkFrame(root, fg_color="white")
login_frame.pack(fill="both", expand=True)

top_row = ctk.CTkFrame(login_frame, fg_color="white", height=38)
top_row.pack(fill="x", side="top")
top_row.pack_propagate(False)

# tk.Label buttons
btn_font = ("Segoe UI", 14, "bold")

def make_lbl(text, cmd, hover="#e0e0e0"):
    lbl = tk.Label(top_row, text=text, font=btn_font,
                   bg="white", fg="#555555", cursor="hand2",
                   width=3, height=1)
    lbl.pack(side="right")
    lbl.bind("<Enter>", lambda e: lbl.configure(bg=hover))
    lbl.bind("<Leave>", lambda e: lbl.configure(bg="white"))
    lbl.bind("<Button-1>", lambda e: (cmd(), "break"))
    return lbl

close_btn = make_lbl("✕", root.destroy, "#ff4444")
min_btn = make_lbl("−", root.iconify, "#e0e0e0")

# Draggable (entire top_row)
def drag_start(e):
    global drag_data
    drag_data = {"x": e.x_root - root.winfo_x(), "y": e.y_root - root.winfo_y()}

def drag_move(e):
    x = e.x_root - drag_data["x"]
    y = e.y_root - drag_data["y"]
    root.geometry(f"+{x}+{y}")

drag_data = {}
top_row.bind("<Button-1>", drag_start)
top_row.bind("<B1-Motion>", drag_move)

# === Center form ===
center = ctk.CTkFrame(login_frame, fg_color="white")
center.place(relx=0.5, rely=0.45, anchor="center")

ctk.CTkLabel(center, text="💬", font=("Segoe UI", 40),
             bg_color="white").pack(pady=(30, 0))
ctk.CTkLabel(center, text="TCP 聊天室", font=("Segoe UI", 22, "bold"),
             text_color="#1a1a1a", bg_color="white").pack(pady=(4, 2))

root.update()

# === DEBUG OUTPUT ===
print("=" * 60)
print(f"Window: {root.winfo_width()}x{root.winfo_height()}")
print(f"login_frame: {login_frame.winfo_width()}x{login_frame.winfo_height()}")
print(f"top_row: {top_row.winfo_width()}x{top_row.winfo_height()} "
      f"pos=({top_row.winfo_x()},{top_row.winfo_y()})")
print()

for child in top_row.winfo_children():
    x, y = child.winfo_x(), child.winfo_y()
    w, h = child.winfo_width(), child.winfo_height()
    cls = child.winfo_class()
    txt = ""
    try: txt = repr(child.cget("text"))
    except: pass
    print(f"  [{cls}] txt={txt:>4} pos=({x:>3},{y:>3}) {w}x{h}")

print()
# Check HWND style
hwnd = ctypes.windll.user32.FindWindowW(None, "DebugLogin")
if hwnd:
    ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
    print(f"HWND: {hwnd}")
    print(f"ExStyle: {ex:#010x} TOOLWINDOW={bool(ex & 0x00000080)}")

print("=" * 60)
print("✓ Window open - verify visually, closes in 8s")
root.after(8000, root.destroy)
root.mainloop()
