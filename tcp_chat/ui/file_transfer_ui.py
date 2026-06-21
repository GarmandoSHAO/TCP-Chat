"""
私聊文件传输管理器 —— 基于 croc，使用 CROC_SECRET 环境变量
"""

import os
import time
import subprocess
import threading
import tkinter.filedialog as filedialog
import logging
import shutil

from ..config import get_app_root

logger = logging.getLogger(__name__)

DEFAULT_DOWNLOAD_DIR = os.path.join(get_app_root(), "download")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

MSG_PREFIX_OFFER = "/file_offer|"
MSG_PREFIX_ACCEPT = "/file_accept|"
MSG_PREFIX_DECLINE = "/file_decline|"


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def find_croc() -> str | None:
    """查找 croc 可执行文件（应用目录优先，其次 PATH）"""
    root = get_app_root()
    croc_exe = "croc.exe" if os.name == "nt" else "croc"
    local = os.path.join(root, croc_exe)
    if os.path.exists(local):
        return os.path.abspath(local)
    which = shutil.which(croc_exe)
    if which:
        return which
    return None


class FileTransferManager:

    def __init__(self, app):
        self.app = app
        self._croc_path = find_croc()
        self._transfers: dict = {}

    # ── 发送 ──────────────────────────────────────────

    def send_file(self, tab, nick):
        if not self._croc_path:
            self._system_msg(tab, "❌ croc 未安装")
            logger.warning("croc未安装，无法发送文件")
            return

        filepath = filedialog.askopenfilename(title="选择要发送的文件")
        if not filepath:
            logger.info("用户取消选择文件")
            return
        logger.info("选择文件: %s (%d bytes)", filepath, os.path.getsize(filepath))

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        tab_id = tab["id"]

        if tab_id in self._transfers:
            self._system_msg(tab, "⚠️ 已有进行中的传输")
            return

        import random
        code = f"chat{random.randint(100000,999999)}"

        state = {
            "direction": "send", "filename": filename,
            "filesize": filesize, "filepath": filepath, "code": code,
            "status": "starting", "process": None,
            "progress": 0.0, "start_time": time.time(),
        }
        logger.info("开始发送线程: %s -> %s (code=%s, %d bytes)", filename, nick, code, filesize)
        self._transfers[tab_id] = state
        self._system_msg(tab, f"📤 {filename}")

        threading.Thread(
            target=self._send_thread, args=(tab, nick, filepath, code, state), daemon=True
        ).start()

    def _send_thread(self, tab, nick, filepath, code, state):
        logger.info("发送线程运行中: file=%s code=%s", os.path.basename(filepath), code)
        try:
            offer_msg = f"{MSG_PREFIX_OFFER}{code}|{state['filename']}|{state['filesize']}"
            self._send_private_msg(nick, offer_msg)
            logger.info("已发送文件邀约至 %s: code=%s", nick, code)
            time.sleep(0.3)
            state["status"] = "transferring"
            self._run_croc_send(tab, state, filepath, code)
        except Exception as e:
            logger.error("croc send error: %s", e, exc_info=True)
        finally:
            logger.info("发送线程结束: %s", os.path.basename(filepath))
            self._safe_call(self._system_msg, tab, "✅ 上传完成")
            state["process"] = None
            self._transfers.pop(tab["id"], None)

    def _run_croc_send(self, tab, state, filepath, code):
        env = {**os.environ, "CROC_SECRET": code}
        logger.info("croc send启动: code=%s file=%s", code, filepath)
        self._safe_call(self._update_progress_msg, tab, f"📤 {state['filename']}    传输中...")
        tab["_ft_prog_txt"] = f"📤 {state['filename']}    传输中..."
        proc = subprocess.Popen(
            [self._croc_path, "send", filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        state["process"] = proc
        try:
            proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            logger.warning("croc send 超时")
            proc.kill()
            proc.wait()
        logger.info("croc send结束: returncode=%s", proc.returncode)
        if proc.returncode in (0, -9):
            total = format_size(state["filesize"])
            self._safe_call(self._update_progress_msg, tab, f"📤 {state['filename']}    {total}/{total}")
            tab["_ft_prog_txt"] = f"📤 {state['filename']}    {total}/{total}"

    # ── 接收 ──────────────────────────────────────────

    def handle_offer(self, tab, sender_nick, content):
        if not self._croc_path:
            self._system_msg(tab, "❌ croc 未安装")
            logger.warning("croc未安装，无法接收文件")
            return
        parts = content.split("|", 3)
        if len(parts) < 4:
            logger.warning("文件邀约格式错误: %s", content)
            return
        _, code, filename, filesize_str = parts
        try:
            filesize = int(filesize_str)
        except ValueError:
            logger.warning("文件大小格式错误: %s", filesize_str)
            return
        logger.info("收到文件邀约: %s -> %s (%d bytes, code=%s)", sender_nick, filename, filesize, code)
        tab_id = tab["id"]
        if tab_id in self._transfers:
            self._system_msg(tab, "⚠️ 已有进行中的传输")
            return
        state = {
            "direction": "receive", "filename": filename,
            "filesize": filesize, "code": code,
            "sender_nick": sender_nick, "status": "offered",
            "process": None, "progress": 0.0, "start_time": time.time(),
        }
        self._transfers[tab_id] = state

        # 保存邀约信息供切换标签后重新显示
        tab["_ft_offer"] = {
            "code": code, "filename": filename,
            "filesize": filesize, "sender_nick": sender_nick,
        }
        tab["_messages"].append(("system", f"📥 文件传输请求: {filename} ({format_size(filesize)})"))

        self._display_offer(tab, filename, filesize, code)

    def _display_offer(self, tab, filename, filesize, code):
        """显示接受/拒绝按钮"""
        tw = tab.get("msg_text")
        if not tw:
            return
        ts = time.strftime("%H:%M")
        tid = tab["id"]
        at = f"ft_acc_{tid}"
        dt = f"ft_dec_{tid}"

        for t_name, fg in [(at, "#075e54"), (dt, "#c62828")]:
            tw.tag_configure(t_name, foreground=fg, underline=True, font=("Segoe UI", 16, "bold"))
        tw.tag_bind(at, "<Button-1>",
                    lambda e, c=code, fn=filename, fs=filesize, tb=tab:
                        self._accept_file(tb, c, fn, fs))
        tw.tag_bind(dt, "<Button-1>",
                    lambda e, fn=filename, tb=tab:
                        self._decline_file(tb, fn))

        if tid in self._transfers:
            self._transfers[tid]["_offer_tags"] = (at, dt)

        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "":
            tw.insert("end", "\n")
        tw.insert("end", f"  {ts}  ", ("timestamp",))
        tw.insert("end", f"📥 文件传输请求", ("system",))
        tw.insert("end", f"\n  📄 {filename}", ("normal",))
        tw.insert("end", f"\n  📦 {format_size(filesize)}", ("normal",))
        tw.insert("end", "\n  ", ("normal",))
        tw.insert("end", "[接受]  ", at)
        tw.insert("end", "[拒绝]", dt)
        tw.insert("end", "\n")
        tw.see("end")
        tw.config(state="disabled")

    def redisplay_offers(self, tab):
        """切换标签后重新显示待处理的文件邀约"""
        offer = tab.get("_ft_offer")
        if not offer:
            return
        state = self._transfers.get(tab["id"])
        if not state or state.get("status") != "offered":
            return
        logger.info("重新显示文件邀约: %s", offer.get("filename"))
        self._display_offer(tab, offer["filename"], offer["filesize"], offer["code"])


    def redisplay_progress(self, tab):
        """切换标签后重新显示传输进度"""
        txt = tab.get("_ft_prog_txt")
        if not txt:
            return
        tab.pop("_ft_prog_start", None)
        tab.pop("_ft_prog_end", None)
        self._update_progress_msg(tab, txt)

    def _accept_file(self, tab, code, filename, filesize):
        logger.info("接受文件: tab=%d code=%s filename=%s", tab["id"], code, filename)
        state = self._transfers.get(tab["id"])
        if not state:
            logger.warning("接受文件失败: state不存在 tab=%d", tab["id"])
            return
        self._clear_offer_buttons(tab, state)
        state["status"] = "transferring"
        self._system_msg(tab, f"📥 {filename}")
        self._send_private_msg(state.get("sender_nick", ""), f"{MSG_PREFIX_ACCEPT}{filename}")
        threading.Thread(
            target=self._receive_thread, args=(tab, code, filename, filesize, state), daemon=True
        ).start()

    def _receive_thread(self, tab, code, filename, filesize, state):
        dl = DEFAULT_DOWNLOAD_DIR
        env = {**os.environ, "CROC_SECRET": code}
        logger.info("接收线程启动: code=%s file=%s", code, filename)
        self._safe_call(self._update_progress_msg, tab, f"📥 下载 {filename}    传输中...")
        try:
            proc = subprocess.Popen(
                [self._croc_path, "--yes", "--out", dl],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                cwd=dl,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            state["process"] = proc
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                logger.warning("croc receive 超时")
                proc.kill()
                proc.wait()
            logger.info("croc recv结束: returncode=%s", proc.returncode)
            if proc.returncode in (0, -9):
                total = format_size(filesize)
                self._safe_call(self._update_progress_msg, tab, f"📥 下载 {filename}    {total}/{total}")
                self._safe_call(self._system_msg, tab, "✅ 接收完成")
            else:
                self._safe_call(self._system_msg, tab, f"❌ 接收失败 ({proc.returncode})")
        except Exception as e:
            logger.error("croc receive error: %s", e, exc_info=True)
            self._safe_call(self._system_msg, tab, "❌ 接收错误")
        finally:
            state["process"] = None
            self._transfers.pop(tab["id"], None)

    def _decline_file(self, tab, filename):
        state = self._transfers.pop(tab["id"], None)
        sender_nick = state.get("sender_nick", "") if state else ""
        if state:
            self._clear_offer_buttons(tab, state)
        self._system_msg(tab, f"❌ 已拒绝 {filename}")
        if sender_nick:
            self._send_private_msg(sender_nick, f"{MSG_PREFIX_DECLINE}{filename}")

    def handle_accept_response(self, sender_nick, content):
        logger.info("对方已接受文件: %s %s", sender_nick, content)

    def handle_decline_response(self, sender_nick, content):
        filename = content.split("|", 1)[1] if "|" in content else ""
        for tid, st in list(self._transfers.items()):
            if st.get("direction") == "send" and st.get("filename") == filename:
                proc = st.get("process")
                if proc:
                    try:
                        proc.terminate()
                        proc.wait(timeout=5)
                    except:
                        try: proc.kill()
                        except: pass
                self._transfers.pop(tid, None)
                break

    def cleanup_tab(self, tab):
        st = self._transfers.pop(tab["id"], None)
        if st and st.get("process"):
            try: st["process"].terminate()
            except: pass

    def cleanup_all(self):
        for st in list(self._transfers.values()):
            if st.get("process"):
                try: st["process"].terminate()
                except: pass
        self._transfers.clear()

    # ── 工具 ──────────────────────────────────────────

    def _system_msg(self, tab, text):
        tw = tab.get("msg_text")
        if not tw:
            return
        tw.config(state="normal")
        if tw.get("end-2c", "end-1c") != "":
            tw.insert("end", "\n")
        tw.insert("end", text, ("system",))
        tw.see("end")
        tw.config(state="disabled")
        tab.setdefault("_messages", []).append(("system", text))


    def _update_progress_msg(self, tab, text):
        """显示进度消息（先删旧的，再追加新的，实现原地刷新）"""
        tw = tab.get("msg_text")
        if not tw:
            return
        tw.config(state="normal")
        # 如果有旧的进度行则先删除
        old_start = tab.get("_ft_prog_start")
        if old_start:
            try:
                old_end = tab.get("_ft_prog_end")
                line_start = tw.index(f"{old_start} linestart")
                tw.delete(line_start, old_end)
            except Exception:
                pass
        else:
            if tw.get("end-2c", "end-1c") != "":
                tw.insert("end", "\n")
        tab["_ft_prog_start"] = tw.index("end-1c")
        tw.insert("end", text, ("system",))
        tab["_ft_prog_end"] = tw.index("end-1c")
        tw.see("end")
        tw.config(state="disabled")

    def _send_private_msg(self, nick, text):
        if not nick or not self.app.sock:
            return
        try:
            self.app.sock.sendall(f"/to {nick} {text}".encode("utf-8"))
        except Exception:
            pass

    def _safe_call(self, func, *args, **kwargs):
        try:
            self.app.root.after(0, func, *args, **kwargs)
        except Exception:
            pass

    def _clear_offer_buttons(self, tab, state):
        tags = state.get("_offer_tags")
        if tags and tab.get("msg_text"):
            for tag in tags:
                try: tab["msg_text"].tag_delete(tag)
                except: pass

    def _find_tab(self, tab_id):
        for t in self.app._tabs:
            if t.get("id") == tab_id:
                return t
        return None
