"""
应用主控 — 聊天客户端用户界面控制器
管理标签页、消息收发、用户列表、私聊、命令菜单
与 InitialInterface（初始界面）完全分离，通过回调通信
"""
import tkinter as tk
import customtkinter as ctk
import socket
import threading
import time
import queue
import re
import os
import sys

from ..config import get, get_local_ip
from ..client import connect_server, start_receive
from .theme import *
from .widgets import make_draggable
from .chat_page import build_chat_view
from .initial_interface import InitialInterface
from . import cache_manager

ctk.set_appearance_mode(get("appearance", "light"))
ctk.set_default_color_theme(get("theme", "green"))


class ChatClientUI:
    """聊天室 GUI 用户界面主控

    职责：
      - 管理主窗口 (root) 和聊天界面
      - 管理多房间标签页 (tabs)
      - 消息收发、用户列表、私聊、命令菜单
      - 通过 InitialInterface 处理创建 / 加入房间
    """

    def __init__(self, auto_connect=None):
        self.root = ctk.CTk()
        self.root.title("TCP 聊天室")
        self.root.withdraw()  # 初始隐藏，有房间后才显示

        # ---- 网络状态 ----
        self.sock = None
        self.nickname = ""
        self.connected = False
        self.msg_queue = queue.Queue()
        self.stop_threads = False
        self.online_users = []
        self._host_id = None
        self._host_name = None
        self._server_thread = None
        self._is_host = False
        self._blocked_users = set()
        self._private_chat_with = None

        # ---- 窗口状态 ----
        self._scale = 1.0
        self._resize_timer = None
        self._base_width = 880
        self._drag_data = {"x": 0, "y": 0}
        self._public_addr = None
        self._tunnel = None
        self.room_id = None           # 当前标签的房间号
        self._joined_room_ids = set() # 已加入的房间号列表（去重用）
        self._chat_built = False  # 用户界面是否已构建
        self._restoring = False   # 是否正在恢复缓存（阻止重复记录）

        # ---- 标签页 ----
        self._tabs = []
        self._active_tab = -1

        # ---- 初始界面 ----
        self._initial_interface = None

        # ---- UI 控件引用（由 _build_user_interface 填充） ----
        self.chat_frame = None
        self.msg_text = None
        self.msg_entry = None
        self.status_bar = None
        self.title_label = None
        self.user_list_inner = None
        self.tab_container = None
        self.user_count_label = None
        self.send_btn = None

        self._set_window_icon()
        self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Configure>", self._on_window_resize)

        if auto_connect:
            host, port, nick = auto_connect
            self.nickname = nick
            self.root.after(200, lambda: self._connect_thread(host, port, nick))
        else:
            self.root.after(200, self._open_initial_interface)

    # ======================== 窗口基础 ========================

    def _set_window_icon(self):
        try:
            img = tk.PhotoImage(width=16, height=16)
            for x in range(16):
                for y in range(16):
                    c = "#075e54"
                    if 3 <= x <= 12 and 3 <= y <= 12:
                        c = "#ffffff"
                    elif 4 <= x <= 11 and 4 <= y <= 11:
                        c = "#075e54"
                    img.put(c, (x, y))
            self.root.iconphoto(True, img)
            self._icon_img = img
        except Exception:
            pass

    # ======================== 初始界面管理 ========================

    def _open_initial_interface(self):
        """打开（或切换至）初始界面窗口"""
        if self._initial_interface is None:
            self._initial_interface = InitialInterface(self.root, self)
        self._initial_interface.show()

    def on_initial_closed(self):
        """初始界面被关闭时的回调"""
        self._initial_interface = None
        # 用户界面从未构建过且没有自动连接 → 退出应用
        if not self._chat_built and not self.sock:
            self.root.destroy()

    def on_room_created(self, nickname, host, port, tunnel=None, server=None):
        """创建房间回调（由 InitialInterface 调用）"""
        self.nickname = nickname
        self._is_host = True
        self._pending_server = server  # 保存 server 实例，后续传给标签页
        # 重置外网地址和隧道（新房间新隧道）
        self._public_addr = None
        self._tunnel = None
        if tunnel:
            self._tunnel = tunnel
            if getattr(tunnel, "public_addr", None):
                self._public_addr = tunnel.public_addr
        self._auto_connect(host, port, nickname)

    def _update_tunnel_addr(self, addr):
        """隧道连接成功（不再需要，各房间通过独立隧道对象读取地址）"""
        pass

    def _is_already_in_room(self, host, port, room_id=None):
        """检查是否已加入该房间

        优先根据房间号判定；无房间号时回退到 host:port 检查
        """
        if room_id and room_id in self._joined_room_ids:
            return True
        for tab in self._tabs:
            if tab.get("host") == host and tab.get("port") == port:
                return True
        return False

    def on_room_joined(self, nickname, host, port, sock, welcome, login,
                       room_id=None, room_name=None):
        """加入房间回调（由 InitialInterface 调用）

        sock 已连接，直接设置接收线程并触发 chat 切换
        如已加入同一房间则忽略
        """
        if self._is_already_in_room(host, port, room_id):
            # 先向服务端发送 /quit 让服务端正确移除用户，再关闭连接
            try:
                sock.sendall("/quit".encode("utf-8"))
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass
            self.msg_queue.put(("MESSAGE", "❌ 已在該房間中，不可重複加入"))
            return

        self.nickname = nickname
        self.sock = sock
        self.connected = True
        self.msg_queue.put(("CONNECTED", {
            "welcome": welcome,
            "login": login,
            "room_id": room_id,
            "room_name": room_name or "",
            "host": host,
            "port": port,
            "nickname": nickname,
        }))
        self.stop_threads = False
        threading.Thread(
            target=start_receive,
            args=(sock, self.msg_queue, lambda: self.stop_threads),
            daemon=True,
        ).start()

    def _on_show_menu(self):
        """'+' 按钮回调：打开初始界面以加入更多房间"""
        self._open_initial_interface()

    # ======================== 用户界面构建（仅一次） ========================

    def _build_user_interface(self):
        """首次构建完整的用户聊天界面"""
        win = get("window", {})
        self.root.geometry(
            f"{win.get('chat_width', 880)}x{win.get('chat_height', 640)}")
        self.root.minsize(700, 500)
        self.root.resizable(True, True)

        chat = build_chat_view(
            self.root, self._send_message, self._disconnect,
            on_menu=self._on_show_menu,
        )
        self.chat_frame = chat["frame"]
        self.msg_text = chat["msg_text"]
        self.msg_entry = chat["msg_entry"]
        self.status_bar = chat["status_bar"]
        self.status_bar.pack_forget()  # 每个标签自带状态条，隐藏顶部全局条
        self.title_label = chat["title_label"]
        self.title_label.pack_forget()  # 房间信息由标签栏展示，隐藏标题
        self.user_list_inner = chat["user_list_inner"]
        self.tab_container = chat["tab_container"]
        self.user_count_label = chat["user_count"]
        self.send_btn = chat["send_btn"]

        make_draggable(chat["top_bar"], self._drag_data)
        self._add_title_context_menu()
        self._build_command_menu()
        self._chat_built = True

    # ======================== 多标签页管理 ========================

    def _on_tab_right_click(self, event, index):
        """标签右键菜单：先切换到该房间，再显示菜单"""
        self._switch_tab(index)
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    def _refresh_tabs(self):
        """刷新标签栏：所有房间用和标题栏一致的样式显示为可点击标签"""
        if not hasattr(self, "tab_container") or not self._tabs:
            return
        # 总是显示标签栏
        self.tab_container.pack(side="left", fill="x", expand=True)
        for w in self.tab_container.winfo_children():
            w.destroy()
        for i, tab in enumerate(self._tabs):
            is_active = (i == self._active_tab)
            frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
            frame.pack(side="left", padx=(2, 0))
            # 状态条
            color = STATUS_GREEN if tab.get("connected") else STATUS_RED
            ctk.CTkFrame(frame, width=3, height=18, fg_color=color,
                         corner_radius=2).pack(side="left", padx=(0, 4))
            # 和标题栏一样漂亮的标签
            bg = CHAT_TITLE if is_active else "white"
            fg = "white" if is_active else CHAT_TITLE
            lbl = ctk.CTkLabel(
                frame, text=tab["name"],
                font=("Segoe UI", 12, "bold"),
                text_color=fg, fg_color=bg,
                corner_radius=6, cursor="hand2",
                padx=8,
            )
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            lbl.bind("<Button-3>", lambda e, idx=i: self._on_tab_right_click(e, idx))
            lbl.bind("<Enter>", lambda e, l=lbl, a=is_active: l.configure(
                fg_color="#e8f5e9" if not a else "#054d44"))
            lbl.bind("<Leave>", lambda e, l=lbl, a=is_active: l.configure(
                fg_color="white" if not a else CHAT_TITLE))

    def _record_message(self, msg_type, text, **kwargs):
        """记录消息到当前标签的缓存列表（恢复模式不记录）"""
        if self._restoring:
            return
        if 0 <= self._active_tab < len(self._tabs):
            self._tabs[self._active_tab]["_messages"].append({
                "type": msg_type, "text": text, **kwargs,
            })
            # 每次收到消息立即写入缓存文件
            self._save_current_tab()

    def _save_current_tab(self):
        """将当前标签的状态写入缓存文件"""
        if self._active_tab < 0 or self._active_tab >= len(self._tabs):
            return
        tab = self._tabs[self._active_tab]
        room_id = tab.get("room_id")
        if not room_id:
            return
        cache_manager.save(room_id, {
            "messages": tab.get("_messages", []),
            "online_users": tab.get("online_users", []),
            "host_id": tab.get("_host_id"),
        })

    def _rebuild_display_from_messages(self, tab):
        """从缓存消息重建 msg_text 显示"""
        if not self.msg_text:
            return
        tw = self.msg_text
        tw.config(state="normal")
        tw.delete("1.0", "end")
        for msg in tab.get("_messages", []):
            mtype = msg.get("type", "system")
            mtext = msg.get("text", "")
            if not mtext:
                continue
            if tw.get("end-2c", "end-1c") != "":
                tw.insert("end", "\n")
            if mtype == "system":
                tw.insert("end", mtext, ("system",))
            elif mtype == "chat":
                is_self = msg.get("is_self", False)
                tw.insert("end", f"  {time.strftime('%H:%M')}  ", ("timestamp",))
                if mtext.startswith("💬 ["):
                    end = mtext.find("]", 3)
                    if end > 0:
                        nick = mtext[3:end]
                        content = mtext[end + 2:]
                        tw.insert("end", nick + (" (我)" if is_self else ""), ("nickname_tag",))
                        tw.insert("end", f"\n{content}", ("normal",))
                    else:
                        tw.insert("end", mtext, ("normal",))
                else:
                    tw.insert("end", mtext, ("normal",))
            elif mtype == "private":
                tw.insert("end", f"  {time.strftime('%H:%M')}  ", ("timestamp",))
                tw.insert("end", mtext, ("private",))
        tw.see("end")
        tw.config(state="disabled")

    def _switch_tab(self, index):
        """切换到指定标签页，保存当前状态并恢复目标状态"""
        if index < 0 or index >= len(self._tabs):
            return
        # 1. 保存当前标签的状态到缓存文件
        self._save_current_tab()

        # 2. 隐藏当前标签内容
        if 0 <= self._active_tab < len(self._tabs):
            old = self._tabs[self._active_tab]
            if old.get("chat_frame"):
                try:
                    old["chat_frame"].pack_forget()
                except Exception:
                    pass

        # 3. 显示新标签
        self._active_tab = index
        tab = self._tabs[index]
        if tab.get("chat_frame"):
            tab["chat_frame"].pack(fill="both", expand=True)

        # 4. 更新全局引用到当前标签
        self.sock = tab.get("sock")
        self.nickname = tab.get("nickname", "")
        self.msg_text = tab.get("msg_text")
        self.msg_entry = tab.get("msg_entry")
        self.user_list_inner = tab.get("user_list_inner")
        self.user_count_label = tab.get("user_count")
        self.status_bar = tab.get("status_bar")
        self.title_label = tab.get("title_label")
        self.send_btn = tab.get("send_btn")
        self.connected = tab.get("connected", False)
        self.room_id = tab.get("room_id")
        self._host = tab.get("host")
        self._port = tab.get("port")
        self._public_addr = tab.get("_public_addr")
        self._tunnel = tab.get("_tunnel")
        if tab.get("sock"):
            self.sock = tab["sock"]

        # 5. 恢复在线用户列表和房主 ID
        self.online_users = tab.get("online_users", [])
        self._host_id = tab.get("_host_id")

        # 6. 重建消息显示
        self._restoring = True
        self._rebuild_display_from_messages(tab)
        self._restoring = False

        # 7. 标题栏保持静态「聊天室」，房间信息在标签中展示

        # 8. 刷新用户列表显示
        self._update_user_list_display(self.online_users)
        self._refresh_tabs()

    # ======================== 连接流程 ========================

    def _switch_to_chat(self, info):
        """连接成功后：构建界面 → 添加标签页 → 显示

        info: {
            "welcome": str, "login": str,
            "room_id": str|None, "host": str, "port": int,
            "nickname": str, "room_name": str,
        }
        """
        welcome_msg = info.get("welcome", "")
        login_result = info.get("login", "")
        room_id = info.get("room_id")
        room_name = info.get("room_name", "")
        host = info.get("host")
        port = info.get("port")
        tab_nickname = info.get("nickname", self.nickname)
        tab_display_name = f"{room_name}-{tab_nickname}" if room_name else tab_nickname

        # 首次使用时构建完整用户界面
        if not self._chat_built:
            self._build_user_interface()

        self.root.deiconify()

        # 为新房间创建标签页（含房间号信息）
        tab_id = len(self._tabs)
        tab = {
            "id": tab_id,
            "name": tab_display_name,
            "sock": self.sock,
            "nickname": tab_nickname,
            "connected": True,
            "online_users": list(self.online_users),
            "chat_frame": self.chat_frame,
            "msg_text": self.msg_text,
            "msg_entry": self.msg_entry,
            "user_list_inner": self.user_list_inner,
            "user_count": self.user_count_label,
            "status_bar": self.status_bar,
            "title_label": self.title_label,
            "send_btn": self.send_btn,
            "room_id": room_id,
            "host": host,
            "port": port,
            "room_name": room_name,
            "_messages": [],        # 聊天记录缓存
            "_host_id": None,       # 房主 ID
            "_public_addr": getattr(self, "_public_addr", None),
            "_tunnel": getattr(self, "_tunnel", None),
            "_server": getattr(self, "_pending_server", None),  # 独立的 server 实例
        }
        self._tabs.append(tab)
        self._pending_server = None  # 清理暂存
        if room_id:
            self._joined_room_ids.add(room_id)
        self._switch_tab(tab_id)

        self._add_system_message("🟢 已连接到聊天室")
        if login_result:
            self._display_message(login_result)

        # 房主开放房间（使用标签页自己的 server 实例）
        if self._is_host:
            srv = tab.get("_server")
            if srv:
                srv.room_status = 1

        self.root.lift()
        self.root.focus_force()
        if self.msg_entry:
            self.msg_entry.focus()

    def _auto_connect(self, host, port, nickname):
        """延迟启动自动连接"""
        self.root.after(300, lambda: self._connect_thread(host, port, nickname))

    def _connect_thread(self, host, port, nick):
        """在后台线程中连接服务端"""
        try:
            sock, welcome, login_result, room_id, room_name = connect_server(host, port, nick)
            self.sock = sock
            self.connected = True
            self.msg_queue.put(("CONNECTED", {
                "welcome": welcome,
                "login": login_result,
                "room_id": room_id,
                "room_name": room_name or "",
                "host": host,
                "port": port,
                "nickname": nick,
            }))
            self.stop_threads = False
            threading.Thread(
                target=start_receive,
                args=(sock, self.msg_queue, lambda: self.stop_threads),
                daemon=True,
            ).start()
        except socket.timeout:
            self.msg_queue.put(("ERROR", "连接超时"))
        except ConnectionRefusedError:
            self.msg_queue.put(("ERROR", "连接被拒绝"))
        except socket.gaierror:
            self.msg_queue.put(("ERROR", f'无法解析地址 "{host}"'))
        except Exception as e:
            self.msg_queue.put(("ERROR", f"连接失败：{e}"))

    # ======================== 消息收发 ========================

    def _send_message(self):
        """发送消息"""
        if not self.connected or not self.sock:
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        self._add_chat_message(f"💬 [{self.nickname}]: {text}", is_self=True)
        try:
            self.sock.sendall(text.encode("utf-8"))
            self.msg_entry.delete(0, "end")
            if text.strip().lower() in ("/quit", "/exit"):
                self._add_system_message("正在退出...")
                self._disconnect()
        except OSError:
            self._add_system_message("❌ 发送失败")
            self._disconnect()

    def _process_queue(self):
        """处理消息队列（在主线程中轮询）"""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "CONNECTED":
                    self._switch_to_chat(data)
                elif msg_type == "MESSAGE":
                    self._display_message(data)
                elif msg_type == "ERROR":
                    # 如果有登录界面的状态标签则更新（连接失败场景）
                    pass
                elif msg_type == "DISCONNECTED":
                    self._add_system_message(f"🔴 {data}")
                    self.connected = False
                    if self.sock:
                        try:
                            self.sock.close()
                        except Exception:
                            pass
                    if self.title_label:
                        self.title_label.configure(text="聊天室 — 已断开")
                    if self.status_bar:
                        self.status_bar.configure(fg_color=STATUS_RED)
        except queue.Empty:
            pass
        if not self.stop_threads:
            self.root.after(100, self._process_queue)

    def _display_message(self, raw_msg):
        """解析并显示一条消息"""
        raw_msg = raw_msg.strip().replace("\r", "")
        if not raw_msg:
            return
        for b in self._blocked_users:
            if raw_msg.startswith(f"💬 [{b}]:"):
                return
            if raw_msg.startswith(f"💬 [私聊]({b}"):
                return
        if raw_msg.startswith("💬 [私聊]("):
            end = raw_msg.find("]")
            if end > 0:
                s = raw_msg[7:end].split("(")[-1].split(")")[0]
                if s == self._private_chat_with and hasattr(self, "_pc_text"):
                    self._add_to_private_chat(raw_msg, s)
                    return
            self._add_private_message(raw_msg)
        elif raw_msg.startswith("📢") or raw_msg.startswith("🔴"):
            self._add_system_message(re.sub(r"\|(\d+)", "", raw_msg))
            self._update_users_from_join_leave(raw_msg)
        elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
            self._add_system_message(raw_msg)
        elif raw_msg.startswith("当前在线"):
            self._parse_user_list(raw_msg)
            display = re.sub(r"\|(\d+)", "", raw_msg) if "|" in raw_msg else raw_msg
            self._add_system_message(display, skip_parse=True)
        elif "==========" in raw_msg:
            self._add_system_message(raw_msg)
        else:
            self._add_chat_message(raw_msg)

    def _add_system_message(self, text, skip_parse=False, tw=None):
        """添加系统消息到消息区"""
        tw = tw or getattr(self, "msg_text", None)
        if not tw:
            return
        display = re.sub(r"\|(\d+)", "", text)
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "":
            tw.insert("end", "\n")
        tw.insert("end", display, ("system",))
        tw.see("end")
        tw.config(state="disabled")
        if "当前在线:" in display and not skip_parse:
            # 用原始文本解析（含 |ID），display 已剥离了 |ID 只用于展示
            self._parse_user_list(text)
        # 缓存记录（仅记录到主消息区，不记录到私聊窗口）
        if tw is self.msg_text and not self._restoring:
            self._record_message("system", display)

    def _add_chat_message(self, text, is_self=False):
        """添加聊天消息到消息区"""
        if not self.msg_text:
            return
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        ts = time.strftime("%H:%M")
        self.msg_text.insert("end", f"  {ts}  ", ("timestamp",))
        if text.startswith("💬 ["):
            end = text.find("]", 3)
            if end > 0:
                nick = text[3:end]
                content = text[end + 2:]
                tag = "nickname_tag"
                self.msg_text.insert("end", nick + (" (我)" if is_self else ""), (tag,))
                self.msg_text.insert("end", f"\n{content}", ("normal",))
            else:
                self.msg_text.insert("end", text, ("normal",))
        else:
            self.msg_text.insert("end", text, ("normal",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")
        self._record_message("chat", text, is_self=is_self)

    def _add_private_message(self, text):
        """添加私聊消息"""
        if not self.msg_text:
            return
        self.msg_text.config(state="normal")
        if self.msg_text.get("end-2c", "end-1c") != "":
            self.msg_text.insert("end", "\n")
        self.msg_text.insert("end", f"  {time.strftime('%H:%M')}  ", ("timestamp",))
        self.msg_text.insert("end", text, ("private",))
        self.msg_text.see("end")
        self.msg_text.config(state="disabled")
        self._record_message("private", text)

    def _add_to_private_chat(self, raw_msg, sender):
        """添加到私聊窗口"""
        if not hasattr(self, "_pc_text") or not self._pc_text:
            return
        content = raw_msg.split(": ", 1)[1] if ": " in raw_msg else raw_msg
        is_me = "你 → " in raw_msg[:20]
        tw = self._pc_text
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "":
            tw.insert("end", "\n")
        tw.insert("end", f"  {time.strftime('%H:%M')}  ", "ts")
        if not is_me:
            tw.insert("end", f"{sender}: {content}\n", "normal")
        else:
            tw.insert("end", f"我: {content}\n", "normal")
        tw.see("end")
        tw.config(state="disabled")

    # ======================== 命令菜单 ========================

    def _build_command_menu(self):
        """构建 / 命令补全弹出菜单"""
        self.cmd_defs = [
            ("/help", "显示帮助"),
            ("/list", "查看在线用户"),
            ("/to <昵称> <消息>", "私聊某人"),
            ("/quit", "退出"),
            ("/exit", "退出"),
        ]
        self.cmd_popup = ctk.CTkToplevel(self.root)
        self.cmd_popup.overrideredirect(True)
        self.cmd_popup.attributes("-topmost", True)
        self.cmd_popup.withdraw()
        popup_frame = ctk.CTkFrame(
            self.cmd_popup, corner_radius=8, fg_color="white",
            border_width=1, border_color="#d0d0d0",
        )
        popup_frame.pack(fill="both", expand=True)
        self.cmd_listbox = tk.Listbox(
            popup_frame, font=("Segoe UI", 11), bd=0,
            highlightthickness=0, bg="#ffffff", fg="#333333",
            activestyle="none", exportselection=False, width=30, height=5,
        )
        self.cmd_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._cmd_selected = -1
        self.msg_entry.bind("<KeyRelease>", self._on_cmd_key)
        self.msg_entry.bind("<Up>", self._on_cmd_up)
        self.msg_entry.bind("<Down>", self._on_cmd_down)
        self.msg_entry.bind("<Escape>", lambda e: self._cmd_hide())
        self.msg_entry.bind("<Return>", self._on_return)
        self.cmd_listbox.bind("<Button-1>", self._on_cmd_click)
        self.cmd_listbox.bind("<Double-Button-1>", self._on_cmd_confirm)

    def _cmd_show(self):
        if self.cmd_listbox.size() == 0:
            return
        x = self.msg_entry.winfo_rootx()
        y = self.msg_entry.winfo_rooty() - self.cmd_popup.winfo_reqheight() - 6
        self.cmd_popup.geometry(f"+{x}+{y}")
        self.cmd_popup.deiconify()
        self._cmd_selected = -1
        self.cmd_listbox.selection_clear(0, tk.END)

    def _cmd_hide(self):
        self.cmd_popup.withdraw()

    def _on_cmd_key(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        self.root.after_idle(self._cmd_filter)

    def _cmd_filter(self):
        text = self.msg_entry.get()
        if not text.startswith("/") or " " in text:
            self._cmd_hide()
            return
        partial = text.lower()
        self.cmd_listbox.delete(0, tk.END)
        for cmd, desc in self.cmd_defs:
            if cmd.lower().startswith(partial):
                self.cmd_listbox.insert(tk.END, f"{cmd:<22s}{desc}")
        if self.cmd_listbox.size() > 0:
            self._cmd_show()
        else:
            self._cmd_hide()

    def _on_cmd_up(self, event):
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        self._cmd_selected = (
            (self._cmd_selected - 1) % size if self._cmd_selected > 0 else size - 1
        )
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        return "break"

    def _on_cmd_down(self, event):
        if not self.cmd_popup.winfo_viewable():
            return
        size = self.cmd_listbox.size()
        if size == 0:
            return
        self._cmd_selected = (
            (self._cmd_selected + 1) % size if self._cmd_selected < size - 1 else 0
        )
        self.cmd_listbox.selection_clear(0, tk.END)
        self.cmd_listbox.selection_set(self._cmd_selected)
        return "break"

    def _on_cmd_click(self, event):
        idx = self.cmd_listbox.nearest(event.y)
        if idx >= 0:
            self._cmd_selected = idx

    def _on_cmd_confirm(self, event):
        self._cmd_insert_selected()

    def _cmd_insert_selected(self):
        if self._cmd_selected < 0 or self._cmd_selected >= self.cmd_listbox.size():
            return
        cmd = self.cmd_listbox.get(self._cmd_selected).split()[0]
        self.msg_entry.delete(0, "end")
        self.msg_entry.insert(0, cmd + " ")
        self.msg_entry.icursor(tk.END)
        self._cmd_hide()
        self.msg_entry.focus_set()

    def _on_return(self, event):
        if hasattr(self, "cmd_popup") and self.cmd_popup.winfo_viewable():
            if self._cmd_selected >= 0:
                self._cmd_insert_selected()
                return "break"
        return self._send_message() or "break"

    # ======================== 用户列表 ========================

    def _parse_user_list(self, text):
        """解析"当前在线: "字符串"""
        if "当前在线:" not in text:
            return
        raw = [u.strip() for u in text.split("当前在线:", 1)[1].split(",") if u.strip()]
        self.online_users = []
        self._host_id = None
        for u in raw:
            is_host = u.startswith("👑")
            u2 = u[1:].strip() if is_host else u
            nick, uid = u2, 0
            if "|" in u2:
                parts = u2.rsplit("|", 1)
                nick = parts[0].strip()
                try:
                    uid = int(parts[1])
                except ValueError:
                    pass
            if is_host:
                self._host_id = uid
            self.online_users.append((nick, uid))
        self._host_name = None
        if self._host_id:
            for n, i in self.online_users:
                if i == self._host_id:
                    self._host_name = n
                    break
        self._update_user_list_display(self.online_users)
        # 同步到当前标签
        if 0 <= self._active_tab < len(self._tabs):
            tab = self._tabs[self._active_tab]
            tab["_host_id"] = self._host_id
            tab["online_users"] = list(self.online_users)

    def _update_user_list_display(self, users):
        """刷新在线用户面板"""
        if not getattr(self, "user_list_inner", None):
            return
        try:
            for w in self.user_list_inner.winfo_children():
                w.destroy()
        except Exception:
            pass
        if not users:
            if self.user_count_label:
                self.user_count_label.configure(text="0 人在线")
            return
        fs = max(10, int(12 * self._scale))
        for nick, uid in users:
            row = ctk.CTkFrame(self.user_list_inner, fg_color="transparent")
            row.pack(fill="x", pady=1, padx=6)
            is_host = uid == self._host_id
            indicator = " 👑 " if is_host else " ● "
            color = HOST_GOLD if is_host else ONLINE_GREEN
            ctk.CTkLabel(
                row, text=indicator, font=("Segoe UI", fs),
                text_color=color,
            ).pack(side="left", padx=(0, 5))
            lbl = ctk.CTkLabel(
                row, text=nick, font=("Segoe UI", fs), anchor="w",
                cursor="hand2" if nick != self.nickname else "",
            )
            lbl.pack(side="left", fill="x", expand=True)
            if nick != self.nickname:
                lbl.bind(
                    "<Button-3>",
                    lambda e, n=nick: self._user_cmenu(e, n),
                )
        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

    def _user_cmenu(self, event, nick):
        """用户右键菜单"""
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label="私聊", command=lambda n=nick: self._start_private_chat(n))
        m.add_separator()
        if nick in self._blocked_users:
            m.add_command(
                label="取消屏蔽",
                command=lambda n=nick: self._toggle_block(n),
            )
        else:
            m.add_command(
                label="屏蔽",
                command=lambda n=nick: self._toggle_block(n),
            )
        try:
            m.post(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _update_users_from_join_leave(self, text):
        """从进入/离开消息更新用户列表"""
        for kw, add in [("进入了聊天室", True), ("离开了聊天室", False)]:
            if kw not in text:
                continue
            raw = text.split(kw)[0].strip().lstrip("📢🔴 ").strip()
            if not raw or "|" not in raw:
                break
            parts = raw.rsplit("|", 1)
            nick = parts[0].strip()
            try:
                uid = int(parts[1])
            except ValueError:
                break
            if add:
                self.online_users.append((nick, uid))
            else:
                self.online_users = [(n, i) for n, i in self.online_users if i != uid]
            self._update_user_list_display(self.online_users)
            # 同步到当前标签
            if 0 <= self._active_tab < len(self._tabs):
                self._tabs[self._active_tab]["online_users"] = list(self.online_users)
            break

    def _toggle_block(self, nick):
        """切换屏蔽用户"""
        if nick in self._blocked_users:
            self._blocked_users.discard(nick)
            self._add_system_message(f"🔓 已取消屏蔽 {nick}")
        else:
            self._blocked_users.add(nick)
            self._add_system_message(f"🔒 已屏蔽 {nick}")
        self._update_user_list_display(self.online_users)

    # ======================== 私聊 ========================

    def _start_private_chat(self, nick):
        """打开私聊窗口"""
        if self._private_chat_with == nick:
            return
        self._private_chat_with = nick
        self._build_private_chat_view(nick)

    def _build_private_chat_view(self, nick):
        """构建私聊界面"""
        self._pc_frame = ctk.CTkFrame(self.chat_frame, fg_color="white")
        self._pc_frame.pack(fill="both", expand=True)
        top = ctk.CTkFrame(self._pc_frame, height=38, fg_color="white", corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkButton(
            top, text="← 返回", font=("Segoe UI", 11), width=50, height=28,
            corner_radius=6, fg_color="white", text_color="#075e54",
            hover_color="#e8f5e9", command=self._close_private_chat,
        ).pack(side="left", padx=4)
        ctk.CTkLabel(
            top, text=f"💬 私聊: {nick}", font=("Segoe UI", 12, "bold"),
            text_color="#075e54", bg_color="white",
        ).pack(side="left", padx=8)

        mf = ctk.CTkFrame(self._pc_frame, fg_color="white")
        mf.pack(fill="both", expand=True)
        mf.grid_rowconfigure(0, weight=1)
        mf.grid_columnconfigure(0, weight=1)
        self._pc_text = tk.Text(
            mf, font=("Segoe UI", 12), wrap="word", state="disabled",
            bd=0, padx=14, pady=10, bg="#ffffff", highlightthickness=0,
        )
        self._pc_text.grid(row=0, column=0, sticky="nsew")
        for name, (fg, ft) in [
            ("system", ("#667781", ("Segoe UI", 9, "italic"))),
            ("normal", ("#000000", ("Segoe UI", 12))),
            ("nick", ("#075e54", ("Segoe UI", 12, "bold"))),
            ("ts", ("#999999", ("Segoe UI", 8))),
        ]:
            self._pc_text.tag_configure(name, foreground=fg, font=ft)

        ib = ctk.CTkFrame(self._pc_frame, height=56, fg_color="transparent", corner_radius=0)
        ib.pack(fill="x", padx=10, pady=(6, 10))
        ib.pack_propagate(False)
        self._pc_entry = ctk.CTkEntry(
            ib, font=("Segoe UI", 12), height=38, corner_radius=20,
            placeholder_text=f"私聊 {nick}...",
        )
        self._pc_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._pc_entry.bind(
            "<Return>",
            lambda e: self._send_private(nick, self._pc_entry, self._pc_text),
        )
        ctk.CTkButton(
            ib, text="发送", font=("Segoe UI", 12, "bold"), width=80, height=38,
            corner_radius=20,
            command=lambda: self._send_private(nick, self._pc_entry, self._pc_text),
        ).pack(side="left")

        if self.msg_entry and self.msg_entry.master:
            self.msg_entry.master.pack_forget()
        self._pc_entry.focus()
        self._add_system_message(f"💬 开始与 {nick} 私聊", tw=self._pc_text)

    def _close_private_chat(self):
        """关闭私聊，恢复主聊天界面"""
        if hasattr(self, "_pc_frame") and self._pc_frame:
            self._pc_frame.destroy()
            self._pc_frame = None
        self._private_chat_with = None
        if self.msg_entry and self.msg_entry.master:
            try:
                self.msg_entry.master.pack(fill="x", padx=10, pady=(6, 10))
            except Exception:
                pass

    def _send_private(self, nick, entry, tw):
        """发送私聊消息"""
        text = entry.get().strip()
        if not text:
            return
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "":
            tw.insert("end", "\n")
        tw.insert("end", f"  {time.strftime('%H:%M')}  ", "ts")
        tw.insert("end", f"你 → {nick}\n{nick}: {text}\n", "normal")
        tw.see("end")
        tw.config(state="disabled")
        entry.delete(0, "end")
        try:
            self.sock.sendall(f"/to {nick} {text}".encode("utf-8"))
        except Exception:
            self._add_system_message("❌ 发送失败", tw=self._pc_text)

    # ======================== 标题右键菜单 ========================

    def _add_title_context_menu(self):
        """标题栏右键菜单"""
        self._ctx_menu = tk.Menu(
            self.root, tearoff=False, font=("Segoe UI", 10),
            bg="white", fg="#333333", activebackground="#e8f5e9",
            activeforeground="#075e54",
        )
        self._ctx_menu.add_command(label="🚪 退出房间", command=self._confirm_disconnect)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="🌐 查看本机 IP", command=self._show_ip)
        if self.title_label:
            self.title_label.bind("<Button-3>", self._show_context_menu)
            self.title_label.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event):
        try:
            self._ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._ctx_menu.grab_release()

    def _show_ip(self):
        """显示本机 IP、隧道地址和房间号（各房间独立）"""
        from ..config import get_local_ip
        port = getattr(self, "_port", 8888) or 8888
        ip = f"{get_local_ip()}:{port}"
        # 只从当前房间的隧道对象读取（各房间独立，不受全局变量覆盖）
        tunnel = getattr(self, "_tunnel", None)
        pub = tunnel.public_addr if (tunnel and getattr(tunnel, "public_addr", None)) else None
        room_id = getattr(self, "room_id", None)
        win = ctk.CTkToplevel(self.root, fg_color="white")
        win.title("网络信息")
        h = 190 if room_id else 160
        win.geometry(f"280x{h}+{self.root.winfo_x() + 60}+{self.root.winfo_y() + 80}")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        frame = ctk.CTkFrame(win, fg_color="white", corner_radius=0)
        frame.pack(expand=True)

        def copy(text):
            win.clipboard_clear()
            win.clipboard_append(text)
            hint.configure(text="✅ 复制成功")
            win.after(1500, lambda: hint.configure(text=""))

        def make_row(label, text):
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(
                row, text=label, font=("Segoe UI", 12), text_color="#333333",
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row, text=text, font=("Segoe UI", 12), width=0, height=28,
                corner_radius=5, fg_color="#e0e0e0", text_color="#333333",
                hover_color="#d0d0d0", command=lambda t=text: copy(t),
            ).pack(side="left")

        make_row("局域网 IP", ip)
        if room_id:
            make_row("房间号", room_id)
        if pub:
            make_row("外网地址", pub)
        hint = ctk.CTkLabel(
            frame, text="", font=("Segoe UI", 10), text_color="#2e7d32",
        )
        hint.pack(pady=(4, 2))
        ctk.CTkButton(
            frame, text="关闭", font=("Segoe UI", 11), width=70, height=28,
            corner_radius=5, fg_color="#075e54", command=win.destroy,
        ).pack()

    # ======================== 窗口缩放 ========================

    def _on_window_resize(self, event):
        if event.widget != self.root:
            return
        if not self._chat_built:
            return
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        self._resize_timer = self.root.after(150, self._apply_font_scaling)

    def _apply_font_scaling(self):
        """根据窗口宽度自适应字体大小"""
        if not self.msg_text:
            return
        w = self.root.winfo_width()
        scale = max(0.7, min(2.0, w / self._base_width))
        if abs(scale - self._scale) < 0.05:
            return
        self._scale = scale
        msg_size = max(10, int(MSG_FONT_SIZE * scale))
        self.msg_text.configure(font=("Segoe UI", msg_size))
        for tag, base in [
            ("normal", msg_size),
            ("nickname_tag", (msg_size, "bold")),
            ("system", (max(8, int(10 * scale)), "italic")),
            ("timestamp", max(7, int(9 * scale))),
        ]:
            self.msg_text.tag_configure(
                tag, font=("Segoe UI", *(base if isinstance(base, tuple) else (base,))),
            )
        if self.msg_entry:
            self.msg_entry.configure(font=("Segoe UI", max(10, int(12 * scale))))
        self._update_user_list_display(self.online_users)

    # ======================== 断开 & 关闭 ========================

    def _confirm_disconnect(self):
        """显示确认弹窗，确定后断开当前连接"""
        win = ctk.CTkToplevel(self.root, fg_color="white")
        win.title("退出房间")
        x = self.root.winfo_x() + 120
        y = self.root.winfo_y() + 100
        win.geometry(f"300x140+{x}+{y}")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        win.grab_set()  # 模态

        ctk.CTkLabel(
            win, text="确定离开房间吗？",
            font=("Segoe UI", 14), text_color="#333333",
        ).pack(pady=(24, 8))

        btn_frame = ctk.CTkFrame(win, fg_color="transparent")
        btn_frame.pack(pady=(8, 0))

        ctk.CTkButton(
            btn_frame, text="确定", font=("Segoe UI", 12, "bold"),
            width=80, height=32, corner_radius=6,
            fg_color="#075e54", hover_color="#054d44",
            command=lambda: (win.destroy(), self._disconnect()),
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            btn_frame, text="取消", font=("Segoe UI", 12),
            width=80, height=32, corner_radius=6,
            fg_color="#e0e0e0", text_color="#333333",
            hover_color="#d0d0d0", command=win.destroy,
        ).pack(side="left")

    def _disconnect(self):
        """断开当前连接"""
        # 删除当前房间的缓存文件
        room_id = getattr(self, "room_id", None)
        if room_id:
            # 先保存一次最新状态
            self._save_current_tab()
            cache_manager.delete(room_id)
        self.stop_threads = True
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.title_label:
            self.title_label.configure(text="聊天室 — 已断开")
        if self.status_bar:
            self.status_bar.configure(fg_color=STATUS_RED)
        if self.msg_entry:
            self.msg_entry.configure(state="disabled")
        if self.send_btn:
            self.send_btn.configure(state="disabled")
        if self._is_host:
            # 使用当前标签页关联的 server 实例，不影响其他房间
            tab = self._tabs[self._active_tab] if 0 <= self._active_tab < len(self._tabs) else None
            srv = tab.get("_server") if tab else None
            if srv:
                try:
                    srv.close_room()
                except Exception:
                    pass
            if self._tunnel:
                try:
                    self._tunnel.stop()
                except Exception:
                    pass
                self._tunnel = None

    def _on_close(self):
        """窗口关闭事件（清除所有缓存）"""
        cache_manager.cleanup()
        self.stop_threads = True
        if self.sock:
            try:
                self.sock.sendall("/quit".encode("utf-8"))
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        # 关闭所有房间的 server（遍历所有标签页）
        for tab in self._tabs:
            srv = tab.get("_server")
            if srv:
                try:
                    srv.close_room()
                except Exception:
                    pass
        # 停用所有隧道
        for tab in self._tabs:
            t = tab.get("_tunnel")
            if t:
                try:
                    t.stop()
                except Exception:
                    pass
        self.root.destroy()

    def run(self):
        """启动主循环"""
        self.root.mainloop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 4:
        ChatClientUI(auto_connect=(sys.argv[1], int(sys.argv[2]), sys.argv[3])).run()
    else:
        ChatClientUI().run()
