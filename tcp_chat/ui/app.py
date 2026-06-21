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
from .file_transfer_ui import FileTransferManager, MSG_PREFIX_OFFER, MSG_PREFIX_ACCEPT, MSG_PREFIX_DECLINE

ctk.set_appearance_mode(get("appearance", "light"))
ctk.set_default_color_theme(get("theme", "green"))

# ── 初始化日志系统 ──
from ..log_config import setup_logging
_log_file = setup_logging()
import logging
logger = logging.getLogger(__name__)
logger.info("=" * 50)
logger.info("程序启动")
logger.info("日志文件: %s", _log_file)
logger.info("=" * 50)


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
        self._my_uid = None       # 当前用户自己的 UID

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

        # ---- 文件传输管理器 ----
        self.ft_manager = FileTransferManager(self)

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
        """设置窗口图标（优先加载用户图标，失败则用内置图标）"""
        try:
            from ..config import get_app_root
            icon_path = os.path.join(get_app_root(), "TCP-Chat-small.png")
            if os.path.exists(icon_path):
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
                self._icon_img = img
                return
        except Exception:
            pass
        # fallback: 内置 16×16 绿色方块
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
        """首次构建完整的用户聊天界面（含永久顶栏 + 可切换内容区）"""
        win = get("window", {})
        self.root.geometry(
            f"{win.get('chat_width', 880)}x{win.get('chat_height', 640)}")
        self.root.minsize(700, 500)
        self.root.resizable(True, True)

        # === 永久顶栏（标签切换时始终可见） ===
        self._perm_top_bar = ctk.CTkFrame(self.root, height=38,
                                           corner_radius=0, fg_color=WHITE)
        self._perm_top_bar.pack(fill="x", side="top")
        self._perm_top_bar.pack_propagate(False)

        # "+" 菜单按钮
        menu_btn = ctk.CTkButton(self._perm_top_bar, text="+", width=28, height=26,
                                  font=("Segoe UI", 16, "bold"),
                                  corner_radius=6,
                                  fg_color=WHITE, text_color="#075e54",
                                  hover_color="#e8f5e9",
                                  command=self._on_show_menu)
        menu_btn.pack(side="left", padx=(6, 2))

        # 标签容器（所有房间/私聊标签在此显示）
        self.tab_container = ctk.CTkFrame(self._perm_top_bar, fg_color="transparent")
        self.tab_container.pack(side="left", fill="x", expand=True)

        make_draggable(self._perm_top_bar, self._drag_data)
        self._add_title_context_menu()

        # === 内容区（标签切换时只切换此区域内的子框架） ===
        self._content_area = ctk.CTkFrame(self.root, fg_color="transparent")
        self._content_area.pack(fill="both", expand=True)

        # 构建房间聊天视图（内容区作为容器）
        chat = build_chat_view(self._content_area, self._send_message, self._disconnect)
        self.chat_frame = chat["frame"]
        self.msg_text = chat["msg_text"]
        self.msg_entry = chat["msg_entry"]
        self.user_list_inner = chat["user_list_inner"]
        self.user_count_label = chat["user_count"]
        self.send_btn = chat["send_btn"]

        self._build_command_menu()
        self._chat_built = True

    # ======================== 多标签页管理 ========================

    def _on_tab_right_click(self, event, index):
        """标签右键菜单：先切换到该标签，再显示菜单"""
        self._switch_tab(index)
        tab = self._tabs[index]
        if tab.get("type") == "private":
            m = tk.Menu(self.root, tearoff=False,
                        font=("Segoe UI", 10), bg="white", fg="#333333",
                        activebackground="#e8f5e9", activeforeground="#075e54")
            m.add_command(label="✕ 关闭私聊",
                          command=lambda idx=index: self._close_private_tab(idx))
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                m.grab_release()
        else:
            try:
                self._ctx_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._ctx_menu.grab_release()

    def _refresh_tabs(self):
        """刷新标签栏：房间标签和私聊标签统一展示"""
        if not hasattr(self, "tab_container"):
            return
        for w in self.tab_container.winfo_children():
            w.destroy()
        if not self._tabs:
            self.tab_container.pack_forget()
            return
        self.tab_container.pack(side="left", fill="x", expand=True)
        for i, tab in enumerate(self._tabs):
            is_active = (i == self._active_tab)
            is_private = tab.get("type") == "private"

            frame = ctk.CTkFrame(self.tab_container, fg_color="transparent")
            frame.pack(side="left", padx=(2, 0))

            # 状态条
            color = STATUS_GREEN if tab.get("connected") else STATUS_RED
            ctk.CTkFrame(frame, width=3, height=18, fg_color=color,
                         corner_radius=2).pack(side="left", padx=(0, 4))

            # 标签配色：私聊用紫色调，房间用绿色调
            if is_active:
                if is_private:
                    bg = "#7b1fa2"  # 深紫
                    fg = "white"
                    hover_bg = "#6a1b9a"
                else:
                    bg = CHAT_TITLE
                    fg = "white"
                    hover_bg = "#054d44"
            else:
                bg = "white"
                fg = CHAT_TITLE if not is_private else "#7b1fa2"
                hover_bg = "#f3e5f5" if is_private else "#e8f5e9"

            lbl = ctk.CTkLabel(
                frame, text=tab["name"],
                font=("Segoe UI", 12, "bold" if not is_private else "normal"),
                text_color=fg, fg_color=bg,
                corner_radius=6, cursor="hand2",
                padx=8,
            )
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            lbl.bind("<Button-3>", lambda e, idx=i: self._on_tab_right_click(e, idx))
            lbl.bind("<Enter>", lambda e, l=lbl, a=is_active, h=hover_bg: l.configure(
                fg_color=h if not a else l.cget("fg_color")))
            lbl.bind("<Leave>", lambda e, l=lbl, a=is_active, b=bg: l.configure(
                fg_color=b if not a else l.cget("fg_color")))

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
        """将当前标签的状态写入缓存文件（私聊标签不缓存）"""
        if self._active_tab < 0 or self._active_tab >= len(self._tabs):
            return
        tab = self._tabs[self._active_tab]
        if tab.get("type") == "private":
            return  # 私聊消息不写入磁盘缓存
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

        # 2. 隐藏当前标签（统一用 view_frame）
        if 0 <= self._active_tab < len(self._tabs):
            old = self._tabs[self._active_tab]
            vf = old.get("view_frame") or old.get("chat_frame")
            if vf:
                try:
                    vf.pack_forget()
                except Exception:
                    pass

        # 3. 显示新标签
        self._active_tab = index
        tab = self._tabs[index]
        vf = tab.get("view_frame") or tab.get("chat_frame")
        if vf:
            vf.pack(fill="both", expand=True)

        # 4. 更新全局引用到当前标签
        self.sock = tab.get("sock")
        self.nickname = tab.get("nickname", "")
        self.msg_text = tab.get("msg_text")
        self.msg_entry = tab.get("msg_entry")
        self.user_list_inner = tab.get("user_list_inner")
        self.user_count_label = tab.get("user_count")
        self.send_btn = tab.get("send_btn")
        self.connected = tab.get("connected", False)
        self.room_id = tab.get("room_id")
        self._host = tab.get("host")
        self._port = tab.get("port")
        self._public_addr = tab.get("_public_addr")
        self._tunnel = tab.get("_tunnel")
        if tab.get("sock"):
            self.sock = tab["sock"]

        # 5. 区分房间标签与私聊标签
        is_private = tab.get("type") == "private"

        if is_private:
            # 私聊标签：恢复消息显示（无用户列表）
            self._rebuild_private_chat_display(tab)
            # 重新显示文件邀约按钮（如有）
            try:
                self.ft_manager.redisplay_offers(tab)
                self.ft_manager.redisplay_progress(tab)
            except Exception:
                pass
        else:
            # 房间标签：恢复在线用户列表和消息
            self.online_users = tab.get("online_users", [])
            self._host_id = tab.get("_host_id")
            self._restoring = True
            self._rebuild_display_from_messages(tab)
            self._restoring = False
            self._update_user_list_display(self.online_users)

        # 6. 刷新标签栏
        self._refresh_tabs()

        # 7. 根据连接状态启用/禁用输入控件
        if self.msg_entry:
            self.msg_entry.configure(state="normal" if self.connected else "disabled")
        if self.send_btn:
            self.send_btn.configure(state="normal" if self.connected else "disabled")

        # 8. 为新激活的文本区应用当前缩放比例
        if self.msg_text and hasattr(self, '_scale'):
            msg_size = max(10, int(MSG_FONT_SIZE * self._scale))
            self.msg_text.configure(font=("Segoe UI", msg_size))
            for tag, base in [
                ("normal", msg_size),
                ("nickname_tag", (msg_size, "bold")),
                ("system", (max(8, int(10 * self._scale)), "italic")),
                ("timestamp", max(7, int(9 * self._scale))),
            ]:
                self.msg_text.tag_configure(
                    tag, font=("Segoe UI", *(base if isinstance(base, tuple) else (base,))),
                )
        if self.msg_entry and hasattr(self, '_scale'):
            self.msg_entry.configure(font=("Segoe UI", max(10, int(12 * self._scale))))

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
        logger.info("连接线程启动: %s:%d nick=%s", host, port, nick)
        try:
            sock, welcome, login_result, room_id, room_name, actual_nick = connect_server(host, port, nick)
            self.sock = sock
            self.connected = True
            logger.info("连接成功: room=%s nick=%s", room_name, actual_nick)
            self.msg_queue.put(("CONNECTED", {
                "welcome": welcome,
                "login": login_result,
                "room_id": room_id,
                "room_name": room_name or "",
                "host": host,
                "port": port,
                "nickname": actual_nick,
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
                    msg, sock_id = data
                    # 只处理属于当前连接的断开消息
                    if sock_id != id(self.sock):
                        continue
                    self._add_system_message(f"🔴 {msg}")
                    self.connected = False
                    # 标记所有共享该 socket 的标签为已断开
                    for t in self._tabs:
                        if t.get("sock") and id(t["sock"]) == sock_id:
                            t["connected"] = False
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
            # 消息格式：💬 [私聊](发送者): 内容  或  💬 [私聊](你 → 目标): 内容
            end_paren = raw_msg.find(")", 7)
            if end_paren > 7:
                inner = raw_msg[7:end_paren]  # "发送者" 或 "你 → 目标"
                if not inner.strip():
                    return  # 空的发送者名，忽略

                # 提取消息内容
                content = raw_msg[end_paren + 1:]
                if content.startswith(": "):
                    content = content[2:]

                # 检测文件传输消息
                if content.startswith(MSG_PREFIX_OFFER):
                    # /file_offer|<address>|<filepath>|<filesize>
                    if "→" in inner:
                        target = inner.split("→")[1].strip()
                        tab = self._get_or_create_private_tab(target)
                        tab["_messages"].append(("system", "📤 已发送文件请求"))
                        if self._active_tab == tab["id"]:
                            tw = tab.get("msg_text")
                            if tw:
                                tw.config(state="normal")
                                if tw.get("end-2c", "end-1c") != "":
                                    tw.insert("end", "\n")
                                tw.insert("end", "📤 已发送文件请求", ("system",))
                                tw.see("end")
                                tw.config(state="disabled")
                    else:
                        sender = inner.strip()
                        # 创建或获取私聊标签
                        tab = self._get_or_create_private_tab(sender)
                        # 在房间聊天区显示通知
                        sz = content.rsplit("|", 1)[-1]
                        try:
                            from .file_transfer_ui import format_size
                            hint = f" ({format_size(int(sz))})" if sz.isdigit() else ""
                        except Exception:
                            hint = ""
                        self._add_system_message(f"📥 {sender} 向你发送了文件{hint}，请切换到私聊查看")
                        self.ft_manager.handle_offer(tab, sender, content)
                    return
                elif content.startswith(MSG_PREFIX_ACCEPT):
                    # 对方接受了文件
                    if "→" in inner:
                        # 自己这边收到对方接受通知
                        target = inner.split("→")[1].strip()
                        self.ft_manager.handle_accept_response(target, content)
                    else:
                        self.ft_manager.handle_accept_response(inner.strip(), content)
                    return
                elif content.startswith(MSG_PREFIX_DECLINE):
                    # 对方拒绝了文件
                    if "→" in inner:
                        target = inner.split("→")[1].strip()
                        self.ft_manager.handle_decline_response(target, content)
                    else:
                        sender = inner.strip()
                        self.ft_manager.handle_decline_response(sender, content)
                    return

                # 普通私聊消息
                if "→" in inner:
                    target = inner.split("→")[1].strip()
                    self._route_private_message(raw_msg, target, is_self=True)
                else:
                    sender = inner.strip()
                    self._route_private_message(raw_msg, sender, is_self=False)
            return
        # 如果在私聊标签页中，将房间消息路由到对应的房间标签缓存
        if 0 <= self._active_tab < len(self._tabs) and self._tabs[self._active_tab].get("type") == "private":
            self._route_to_room_tab(raw_msg)
            return
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

    def _route_to_room_tab(self, raw_msg):
        """在私聊标签页中接收房间消息时，直接存入房间标签缓存"""
        current = self._tabs[self._active_tab]
        rid = current.get("room_id")
        for tab in self._tabs:
            if tab.get("type") != "private" and tab.get("room_id") == rid:
                if raw_msg.startswith("📢") or raw_msg.startswith("🔴"):
                    display = re.sub(r"\|(\d+)", "", raw_msg)
                    tab["_messages"].append({"type": "system", "text": display})
                    self._update_users_from_join_leave(raw_msg)
                    # 同步房间标签的在线用户列表
                    tab["online_users"] = list(self.online_users)
                elif raw_msg.startswith("当前在线"):
                    self._parse_user_list(raw_msg)
                    tab["online_users"] = list(self.online_users)
                elif any(raw_msg.startswith(p) for p in ("✅", "❌", "🟢")):
                    tab["_messages"].append({"type": "system", "text": raw_msg})
                elif "==========" in raw_msg:
                    tab["_messages"].append({"type": "system", "text": raw_msg})
                else:
                    tab["_messages"].append({"type": "chat", "text": raw_msg, "is_self": False})
                break

    def _route_private_message(self, raw_msg, nick, is_self=False):
        """将私聊消息路由到对应的私聊标签页"""
        # 查找对应的私聊标签
        target_tab = None
        for tab in self._tabs:
            if tab.get("type") == "private" and tab.get("target_nick") == nick:
                target_tab = tab
                break

        content = raw_msg.split(": ", 1)[1] if ": " in raw_msg else raw_msg
        ts = time.strftime("%H:%M")

        if target_tab:
            display = f"  {ts}  我 → {nick}\n{content}\n" if is_self else f"  {ts}  {nick}\n{content}\n"
            # 只缓存，不插入文本控件（is_self 时 _send_pc 已做本地回显）
            target_tab["_messages"].append(("normal", display))

            # 非自身回显才直接更新显示（自己的消息已由 _send_pc 显示）
            if not is_self and self._active_tab == target_tab["id"]:
                tw = target_tab.get("msg_text")
                if tw:
                    tw.config(state="normal")
                    if tw.get("end-2c", "end-1c") != "":
                        tw.insert("end", "\n")
                    tw.insert("end", display, ("normal",))
                    tw.see("end")
                    tw.config(state="disabled")
        else:
            if is_self:
                # 自己发出的回显，应有标签（以防万一还是显示到主区）
                self._add_private_message(raw_msg)
            else:
                # 别人发来的私聊 → 自动创建私聊标签
                tab = self._create_private_tab_silent(nick)
                display = f"  {ts}  {nick}\n{content}\n"
                tab["_messages"].append(("normal", display))
                # 如果该标签正好是活动标签，直接更新显示
                if self._active_tab == tab["id"]:
                    tw = tab.get("msg_text")
                    if tw:
                        tw.config(state="normal")
                        if tw.get("end-2c", "end-1c") != "":
                            tw.insert("end", "\n")
                        tw.insert("end", display, ("normal",))
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
        # 找出当前用户自己的 UID（按昵称匹配，用第一个出现的）
        for n, uid in self.online_users:
            if n == self.nickname:
                self._my_uid = uid
                break

        self._update_user_list_display(self.online_users)
        # 同步到当前标签
        if 0 <= self._active_tab < len(self._tabs):
            tab = self._tabs[self._active_tab]
            tab["_host_id"] = self._host_id
            tab["online_users"] = list(self.online_users)

    def _update_user_list_display(self, users):
        """刷新在线用户面板—标签卡片样式"""
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
            is_host = uid == self._host_id
            is_self = (uid == self._my_uid)

            # 配色
            if is_host:
                bg = "#fff8e1"
                hover_bg = "#ffecb3"
            elif is_self:
                bg = "#f5f5f5"
                hover_bg = "#e0e0e0"
            else:
                bg = "#f0fdf4"
                hover_bg = "#c8f0d0"

            # row 用实色背景做卡片（CTkFrame），
            # CTkLabel 保持默认透明（原版已验证右键可用）
            row = ctk.CTkFrame(self.user_list_inner, fg_color=bg,
                               corner_radius=8, border_width=0)
            row.pack(fill="x", pady=1, padx=4)

            indicator = "👑" if is_host else "  ● "
            icolor = HOST_GOLD if is_host else ONLINE_GREEN
            ind_lbl = ctk.CTkLabel(
                row, text=indicator, font=("Segoe UI", fs + 2),
                text_color=icolor, fg_color=bg,
            )
            ind_lbl.pack(side="left", padx=(6, 2))

            lbl = ctk.CTkLabel(
                row, text=nick, font=("Segoe UI", fs),
                anchor="w",
                cursor="hand2" if not is_self else "",
            )
            lbl.pack(side="left", fill="x", expand=True)

            # 右键（和原版完全一致）
            if not is_self:
                lbl.bind("<Button-3>", lambda e, n=nick: self._user_cmenu(e, n))

            # 悬停变色（ind_lbl + row + lbl 全更新）
            def _enter(e, r=row, i=ind_lbl, h=hover_bg):
                r.configure(fg_color=h)
                i.configure(fg_color=h)
            def _leave(e, r=row, i=ind_lbl, b=bg):
                r.configure(fg_color=b)
                i.configure(fg_color=b)
            for w in (row, lbl, ind_lbl):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)

        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

        if self.user_count_label:
            self.user_count_label.configure(text=f"{len(users)} 人在线")

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

    def _rebuild_private_chat_display(self, tab):
        """从缓存重建私聊消息显示"""
        tw = tab.get("msg_text")
        if not tw:
            return
        tw.config(state="normal")
        tw.delete("1.0", "end")
        for item in tab.get("_messages", []):
            try:
                if isinstance(item, tuple) and len(item) == 2:
                    mtype, text = item
                elif isinstance(item, dict):
                    mtype = item.get("type", "normal")
                    text = item.get("text", "")
                else:
                    continue
                if not text:
                    continue
                if tw.get("end-2c", "end-1c") != "":
                    tw.insert("end", "\n")
                tag = "system" if mtype == "system" else "normal"
                tw.insert("end", text, (tag,))
            except Exception:
                continue
        tw.see("end")
        tw.config(state="disabled")

    def _create_private_tab_silent(self, nick):
        """创建私聊标签（不切换标签），返回 tab 字典"""
        # 检查是否已存在
        for tab in self._tabs:
            if tab.get("type") == "private" and tab.get("target_nick") == nick:
                return tab

        tab_id = len(self._tabs)

        # ---- 构建私聊视图（顶栏由永久顶栏统一管理） ----
        private_frame = ctk.CTkFrame(self._content_area, fg_color="transparent")

        # ---- 主体 ----
        main_area = ctk.CTkFrame(private_frame, fg_color="transparent")
        main_area.pack(fill="both", expand=True, padx=0, pady=0)

        # === 消息区（与房间完全一致） ===
        msg_container = ctk.CTkFrame(main_area, fg_color="transparent")
        msg_container.pack(side="left", fill="both", expand=True)

        separator = ctk.CTkFrame(main_area, width=1, fg_color="#d0d0d0",
                                 corner_radius=0)
        separator.pack(side="left", fill="y")

        msg_frame = ctk.CTkFrame(msg_container, fg_color=WHITE, corner_radius=0)
        msg_frame.pack(fill="both", expand=True)
        msg_frame.grid_rowconfigure(0, weight=1)
        msg_frame.grid_columnconfigure(0, weight=1)

        pc_text = tk.Text(msg_frame, font=("Segoe UI", MSG_FONT_SIZE),
                           wrap="word", state="disabled",
                           bd=0, padx=14, pady=10, bg="#ffffff",
                           highlightthickness=0)
        pc_text.grid(row=0, column=0, sticky="nsew")

        # 与房间相同的 tag 配置（共享同一组颜色常量）
        for name, (fg, font) in [
            ("system", (SYSTEM_FG, ("Segoe UI", 9, "italic"))),
            ("private", (PRIVATE_FG, ("Segoe UI", 10))),
            ("error", (ERROR_FG, ("Segoe UI", 10, "bold"))),
            ("timestamp", (TIMESTAMP_FG, ("Segoe UI", 8))),
            ("nickname_tag", (NICKNAME_FG, ("Segoe UI", MSG_FONT_SIZE, "bold"))),
            ("normal", ("#000000", ("Segoe UI", MSG_FONT_SIZE))),
        ]:
            pc_text.tag_configure(name, foreground=fg, font=font)

        # 滚动条（与房间相同的 auto-hide 逻辑）
        scrollbar = ctk.CTkScrollbar(msg_frame, command=pc_text.yview,
                                      orientation="vertical", corner_radius=CR)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 2))

        _scroll_timer = [None]

        def _auto_hide_scroll():
            if _scroll_timer[0]:
                msg_frame.after_cancel(_scroll_timer[0])
            _scroll_timer[0] = msg_frame.after(1500, scrollbar.grid_remove)

        def _on_scroll(first, last):
            scrollbar.set(first, last)
            if first == "0.0" and last == "1.0":
                scrollbar.grid_remove()
            else:
                scrollbar.grid()

        def _on_mw(event):
            pc_text.yview_scroll(int(-1 * event.delta / 120), "units")
            first, last = pc_text.yview()
            if first != "0.0" or last != "1.0":
                scrollbar.grid()
                _auto_hide_scroll()
            return "break"

        pc_text.config(yscrollcommand=_on_scroll)
        scrollbar.grid_remove()
        pc_text.bind("<MouseWheel>", _on_mw)
        msg_frame.bind("<MouseWheel>", _on_mw)

        # === 右侧操作面板（替代房间的用户列表） ===
        action_panel = ctk.CTkFrame(main_area, width=190, fg_color=WHITE,
                                     corner_radius=0, border_width=0)
        action_panel.pack(side="right", fill="y")
        action_panel.pack_propagate(False)

        ctk.CTkLabel(action_panel, text="🔧 快捷操作",
                     font=("Segoe UI", 12, "bold"),
                     text_color=CHAT_TITLE, bg_color=WHITE).pack(
                         anchor="w", padx=14, pady=(16, 2))

        # 功能按钮区（以后可在此扩展）
        btn_frame = ctk.CTkFrame(action_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(8, 0))

        action_btns = [
            ("📁 发送文件", lambda n=nick: (
                lambda t: t and self.ft_manager.send_file(t, n)
            )(self._find_private_tab(n))),
            ("📋 用户信息", lambda: self._add_system_message(
                f"📋 {nick} 的信息功能待扩展")),
            ("🔇 屏蔽用户", lambda n=nick: self._toggle_block(n)),
        ]
        for text, cmd in action_btns:
            ctk.CTkButton(btn_frame, text=text,
                          font=("Segoe UI", 11),
                          height=32, corner_radius=6,
                          fg_color="#f5f5f5", text_color="#333333",
                          hover_color="#e0e0e0",
                          anchor="w",
                          command=cmd).pack(fill="x", pady=3)

        # === 输入区（与房间一致） ===
        input_bar = ctk.CTkFrame(private_frame, height=56, fg_color="transparent",
                                  corner_radius=0)
        input_bar.pack(fill="x", padx=10, pady=(6, 10))
        input_bar.pack_propagate(False)

        pc_entry = ctk.CTkEntry(input_bar, font=("Segoe UI", 12),
                                 height=38, corner_radius=CR,
                                 placeholder_text=f"私聊 {nick}...")
        pc_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # 发送回调（通过昵称查找 tab，不依赖 tab_id 闭包）
        def _send_pc(n=nick, entry=pc_entry, tw=pc_text):
            text = entry.get().strip()
            if not text:
                return
            ts = time.strftime("%H:%M")
            display = f"  {ts}  我 → {n}\n{text}\n"
            tw.config(state="normal")
            if tw.get("end-2c", "end-1c") != "":
                tw.insert("end", "\n")
            tw.insert("end", display, ("normal",))
            tw.see("end")
            tw.config(state="disabled")
            entry.delete(0, "end")
            # 实际发送（消息缓存在服务端回显时由 _route_private_message 处理）
            try:
                self.sock.sendall(f"/to {n} {text}".encode("utf-8"))
            except Exception:
                pass

        pc_entry.bind("<Return>", lambda e: _send_pc())

        send_btn = ctk.CTkButton(input_bar, text="发送",
                                  font=("Segoe UI", 12, "bold"),
                                  width=80, height=38,
                                  corner_radius=CR, command=_send_pc)
        send_btn.pack(side="left")

        # 初始系统消息
        sys_msg = f"💬 开始与 {nick} 私聊"
        pc_text.config(state="normal")
        pc_text.insert("end", sys_msg, ("system",))
        pc_text.config(state="disabled")

        # ---- 创建标签条目 ----
        tab = {
            "id": tab_id,
            "name": f"{self.nickname}—{nick}",
            "type": "private",
            "target_nick": nick,
            "sock": self.sock,
            "nickname": self.nickname,
            "connected": True,
            "view_frame": private_frame,
            "msg_text": pc_text,
            "msg_entry": pc_entry,
            "room_id": self.room_id,
            "_messages": [("system", sys_msg)],
        }
        self._tabs.append(tab)
        self._refresh_tabs()
        return tab

    def _start_private_chat(self, nick):
        """打开私聊标签页（由用户主动点击触发，切换到该标签）"""
        # 检查是否已存在该用户的私聊标签
        for tab in self._tabs:
            if tab.get("type") == "private" and tab.get("target_nick") == nick:
                self._switch_tab(tab["id"])
                return

        # 检查该用户是否在线
        if nick not in [n for n, _ in self.online_users]:
            return

        # 保存当前标签状态，创建（或获取）私聊标签并切换
        self._save_current_tab()
        tab = self._create_private_tab_silent(nick)
        self._switch_tab(tab["id"])

    # ── 文件传输辅助 ──────────────────────────────

    def _find_private_tab(self, nick):
        """通过昵称查找私聊标签"""
        for tab in self._tabs:
            if tab.get("type") == "private" and tab.get("target_nick") == nick:
                return tab
        return None

    def _get_or_create_private_tab(self, nick):
        """获取或创建私聊标签（不切换）"""
        tab = self._find_private_tab(nick)
        if not tab:
            tab = self._create_private_tab_silent(nick)
        return tab

    def _close_private_tab(self, tab_id):
        """关闭私聊标签页"""
        if tab_id < 0 or tab_id >= len(self._tabs):
            return
        tab = self._tabs[tab_id]
        if tab.get("type") != "private":
            return

        # 清理文件传输
        self.ft_manager.cleanup_tab(tab)

        # 销毁视图
        try:
            tab["view_frame"].destroy()
        except Exception:
            pass

        # 从标签列表移除
        self._tabs.pop(tab_id)
        # 重建索引
        for i, t in enumerate(self._tabs):
            t["id"] = i

        # 切换到其他标签
        if self._tabs:
            new_idx = min(tab_id, len(self._tabs) - 1)
            self._switch_tab(new_idx)
        else:
            self._active_tab = -1

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
        """断开当前连接并移除标签页（同时移除关联私聊标签）"""
        if self._active_tab < 0 or self._active_tab >= len(self._tabs):
            return
        tab = self._tabs[self._active_tab]
        # 私聊标签不允许从 _disconnect 关闭（应通过 _close_private_tab）
        if tab.get("type") == "private":
            return

        room_id = tab.get("room_id")
        tab_sock = tab.get("sock")

        # 1. 删除缓存
        if room_id:
            self._save_current_tab()
            cache_manager.delete(room_id)
            self._joined_room_ids.discard(room_id)

        # 2. 关闭当前房间的 socket
        if tab_sock:
            try:
                tab_sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                tab_sock.close()
            except Exception:
                pass

        # 3. 关闭 server / 隧道
        if tab.get("_server"):
            try:
                tab["_server"].close_room()
            except Exception:
                pass
        if tab.get("_tunnel"):
            try:
                tab["_tunnel"].stop()
            except Exception:
                pass

        # 4. 从标签列表中移除当前房间标签以及关联的私聊标签
        removed_idx = self._active_tab
        self._tabs.pop(removed_idx)

        # 同时移除绑定同一 room_id 的私聊标签
        private_to_remove = [
            i for i, t in enumerate(self._tabs)
            if t.get("type") == "private" and t.get("room_id") == room_id
        ]
        for i in reversed(private_to_remove):
            pt = self._tabs[i]
            if pt.get("view_frame"):
                try:
                    pt["view_frame"].destroy()
                except Exception:
                    pass
            self._tabs.pop(i)

        # 重建索引
        for i, t in enumerate(self._tabs):
            t["id"] = i

        # 5. 切到其他房间，或关闭界面
        if self._tabs:
            new_idx = min(removed_idx, len(self._tabs) - 1)
            self._switch_tab(new_idx)
        else:
            self._active_tab = -1
            self.connected = False
            self.sock = None
            if self.msg_entry:
                self.msg_entry.configure(state="disabled")
            if self.send_btn:
                self.send_btn.configure(state="disabled")
            # 清空消息区，显示引导文字
            if self.msg_text:
                self.msg_text.config(state="normal")
                self.msg_text.delete("1.0", "end")
                self.msg_text.insert("end",
                    "点击左上角 [+] 按钮来创建或加入聊天房间吧",
                    ("system",))
                self.msg_text.config(state="disabled")
            # 清空用户列表
            if self.user_list_inner:
                for w in self.user_list_inner.winfo_children():
                    w.destroy()
            if self.user_count_label:
                self.user_count_label.configure(text="0 人在线")
            if self.title_label:
                self.title_label.configure(text="聊天室")
            if self.status_bar:
                self.status_bar.configure(fg_color=STATUS_RED)
            self._refresh_tabs()

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

        # 清理文件传输
        try:
            self.ft_manager.cleanup_all()
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
