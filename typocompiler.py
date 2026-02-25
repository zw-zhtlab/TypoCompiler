# typocompiler.py
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from config_manager import ConfigManager
from i18n import (
    t,
    set_language,
    get_language,
    register_listener,
    unregister_listener,
    get_supported_languages,
)
from styles import StyleManager, BUILTIN_STYLES
from llm_client import LLMClient
from file_ops import read_text_utf8, write_text_utf8

APP_NAME = "TypoCompiler"

class TypoCompilerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x600")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.cfg = ConfigManager()
        raw_lang = self.cfg.get("language", "zh")
        set_language(raw_lang)
        effective_lang = get_language()
        if effective_lang != raw_lang:
            self.cfg.set("language", effective_lang)
        self.styles = StyleManager(self.cfg)
        self.llm = LLMClient(self.cfg, self.styles)

        self.current_file: Optional[str] = None
        raw_font_size = self.cfg.get("font_size", 12)
        self.font_size = self._normalize_font_size(raw_font_size)
        if raw_font_size != self.font_size:
            self.cfg.set("font_size", self.font_size)
        self.dirty = False

        self.create_widgets()
        self.apply_font_size()
        self.set_clean_state()
        self.update_title()
        self.status_var.set(t("status.ready"))

        register_listener(self.on_lang_changed)

        if self.cfg.consume_reset_notice():
            messagebox.showinfo(APP_NAME, t("info.reset_defaults"))

    @staticmethod
    def _normalize_font_size(value) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 12
        return max(8, min(40, size))

    def create_widgets(self):
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        # File
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label=t("file.new"), command=self.new_file)
        self.file_menu.add_command(label=t("file.open"), command=self.open_file)
        self.file_menu.add_command(label=t("file.save"), command=self.save_file)
        self.file_menu.add_command(label=t("file.save_as"), command=self.save_file_as)
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=t("file.recent"), menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=t("file.exit"), command=self.on_close)
        self.menubar.add_cascade(label=t("menu.file"), menu=self.file_menu)
        self.refresh_recent_files_menu()

        # Settings
        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.lang_var = tk.StringVar(value=get_language())
        self.rebuild_language_menu()
        self.settings_menu.add_cascade(label=t("settings.language"), menu=self.lang_menu)

        self.style_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.default_style_var = tk.StringVar(value=self.cfg.get("default_style", "Python"))
        self.rebuild_style_menu()
        self.settings_menu.add_cascade(label=t("settings.default_style"), menu=self.style_menu)
        self.settings_menu.add_command(label=t("settings.manage_styles"), command=self.open_manage_styles)

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label=t("settings.llm"), command=self.open_llm_settings)
        self.settings_menu.add_command(label=t("settings.test_llm"), command=self.test_llm)

        self.settings_menu.add_separator()
        font_menu = tk.Menu(self.settings_menu, tearoff=0)
        font_menu.add_command(label=t("settings.font.inc"), command=lambda: self.adjust_font(1))
        font_menu.add_command(label=t("settings.font.dec"), command=lambda: self.adjust_font(-1))
        font_menu.add_command(label=t("settings.font.reset"), command=lambda: self.reset_font())
        self.settings_menu.add_cascade(label=t("settings.font"), menu=font_menu)

        self.menubar.add_cascade(label=t("menu.settings"), menu=self.settings_menu)

        # Run
        self.run_menu = tk.Menu(self.menubar, tearoff=0)
        self.run_menu.add_command(label=t("run.open"), command=self.open_run_window)
        self.menubar.add_cascade(label=t("menu.run"), menu=self.run_menu)

        # 编辑器
        self.text = tk.Text(self, wrap="word", undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.bind("<<Modified>>", self.on_text_modified)

        # 状态栏
        self.status_var = tk.StringVar(value="")
        self.status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(side="bottom", fill="x")

    def on_lang_changed(self, lang: str):
        self.lang_var.set(lang)
        self.update_title()
        self.menubar.delete(0, "end")

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label=t("file.new"), command=self.new_file)
        self.file_menu.add_command(label=t("file.open"), command=self.open_file)
        self.file_menu.add_command(label=t("file.save"), command=self.save_file)
        self.file_menu.add_command(label=t("file.save_as"), command=self.save_file_as)
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=t("file.recent"), menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=t("file.exit"), command=self.on_close)
        self.menubar.add_cascade(label=t("menu.file"), menu=self.file_menu)
        self.refresh_recent_files_menu()

        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.rebuild_language_menu()
        self.settings_menu.add_cascade(label=t("settings.language"), menu=self.lang_menu)

        self.style_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.rebuild_style_menu()
        self.settings_menu.add_cascade(label=t("settings.default_style"), menu=self.style_menu)
        self.settings_menu.add_command(label=t("settings.manage_styles"), command=self.open_manage_styles)

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label=t("settings.llm"), command=self.open_llm_settings)
        self.settings_menu.add_command(label=t("settings.test_llm"), command=self.test_llm)

        self.settings_menu.add_separator()
        font_menu = tk.Menu(self.settings_menu, tearoff=0)
        font_menu.add_command(label=t("settings.font.inc"), command=lambda: self.adjust_font(1))
        font_menu.add_command(label=t("settings.font.dec"), command=lambda: self.adjust_font(-1))
        font_menu.add_command(label=t("settings.font.reset"), command=lambda: self.reset_font())
        self.settings_menu.add_cascade(label=t("settings.font"), menu=font_menu)
        self.menubar.add_cascade(label=t("menu.settings"), menu=self.settings_menu)

        self.run_menu = tk.Menu(self.menubar, tearoff=0)
        self.run_menu.add_command(label=t("run.open"), command=self.open_run_window)
        self.menubar.add_cascade(label=t("menu.run"), menu=self.run_menu)

        self._set_ready_status()

    def refresh_recent_files_menu(self):
        self.recent_menu.delete(0, "end")
        recents = self.cfg.get("recent_files", [])
        if not recents:
            self.recent_menu.add_command(label=t("recent.empty"), state="disabled")
            return
        for path in recents:
            self.recent_menu.add_command(label=path, command=lambda p=path: self.open_file_from_path(p))

    def change_language(self):
        lang = self.lang_var.get()
        set_language(lang)
        self.cfg.set("language", lang)

    def rebuild_language_menu(self):
        self.lang_menu.delete(0, "end")
        for code in get_supported_languages():
            self.lang_menu.add_radiobutton(
                label=t(f"settings.lang.{code}"),
                value=code,
                variable=self.lang_var,
                command=self.change_language,
            )

    def on_default_style_changed(self):
        style = self.default_style_var.get()
        self.cfg.set("default_style", style)

    def rebuild_style_menu(self):
        self.style_menu.delete(0, "end")
        for name in self.styles.names:
            self.style_menu.add_radiobutton(label=name, value=name, variable=self.default_style_var, command=self.on_default_style_changed)

    def on_styles_changed(self):
        self.styles.reload()
        current = self.default_style_var.get()
        if current not in self.styles.names:
            fallback = self.styles.names[0] if self.styles.names else ""
            if fallback:
                self.default_style_var.set(fallback)
                self.cfg.set("default_style", fallback)
        self.rebuild_style_menu()
        for child in self.winfo_children():
            if isinstance(child, RunWindow):
                try:
                    child.refresh_styles()
                except Exception:
                    pass

    def open_manage_styles(self):
        StylesDialog(self, self.styles, self.cfg, on_changed=self.on_styles_changed)

    def open_llm_settings(self):
        LLMSettingsDialog(self, self.cfg, self.llm)

    def test_llm(self):
        if getattr(self, "_testing_llm", False):
            return
        self._testing_llm = True
        self.status_var.set(t("status.testing_llm"))
        threading.Thread(target=self._do_test_llm, daemon=True).start()

    def _do_test_llm(self):
        try:
            ok, msg = self.llm.test_connectivity()
        except Exception as e:
            ok, msg = False, str(e)
        self.after(0, lambda: self._finish_test_llm(ok, msg))

    def _finish_test_llm(self, ok: bool, msg: str):
        self._testing_llm = False
        if ok:
            messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=msg))
        self._set_ready_status()

    def adjust_font(self, delta: int):
        self.font_size = max(8, min(40, self.font_size + delta))
        self.apply_font_size()
        self.cfg.set("font_size", self.font_size)

    def reset_font(self):
        self.font_size = 12
        self.apply_font_size()
        self.cfg.set("font_size", self.font_size)

    def apply_font_size(self):
        font = ("TkFixedFont", self.font_size)
        self.text.configure(font=font)

    def update_title(self):
        base = t("app.title")
        if self.current_file:
            base += f" - {os.path.basename(self.current_file)}"
        if self.dirty:
            base += " *"
        self.title(base)

    def set_clean_state(self):
        self.dirty = False
        try:
            self.text.edit_modified(False)
        except Exception:
            pass

    def on_text_modified(self, evt=None):
        if self.text.edit_modified():
            self.dirty = True
            self.update_title()
            self.text.edit_modified(False)

    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        return messagebox.askyesno(APP_NAME, t("warn.unsaved"))

    def _set_ready_status(self):
        if self.current_file:
            self.status_var.set(t("status.loaded", name=os.path.basename(self.current_file)))
        else:
            self.status_var.set(t("status.ready"))

    def new_file(self):
        if not self.confirm_discard():
            return
        self.text.delete("1.0", "end")
        self.current_file = None
        self.set_clean_state()
        self.update_title()
        self.status_var.set(t("status.ready"))

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        self.open_file_from_path(path)

    def open_file_from_path(self, path: str):
        if not self.confirm_discard():
            return
        try:
            content = read_text_utf8(path)
            self.text.delete("1.0", "end")
            self.text.insert("1.0", content)
            self.current_file = path
            self.cfg.add_recent_file(path)
            self.refresh_recent_files_menu()
            self.set_clean_state()
            self.update_title()
            self.status_var.set(t("status.loaded", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.open_failed", err=str(e)))

    def save_file(self):
        if not self.current_file:
            return self.save_file_as()
        try:
            write_text_utf8(self.current_file, self.text.get("1.0", "end-1c"))
            self.set_clean_state()
            self.update_title()
            self.status_var.set(t("status.saved", name=os.path.basename(self.current_file)))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.save_failed", err=str(e)))

    def save_file_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        try:
            write_text_utf8(path, self.text.get("1.0", "end-1c"))
            self.current_file = path
            self.cfg.add_recent_file(path)
            self.refresh_recent_files_menu()
            self.set_clean_state()
            self.update_title()
            self.status_var.set(t("status.saved", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.save_failed", err=str(e)))

    def open_run_window(self):
        RunWindow(self, self.cfg, self.styles, self.llm, self.text.get("1.0", "end-1c"))

    def on_close(self):
        if not self.confirm_discard():
            return
        try:
            unregister_listener(self.on_lang_changed)
        except Exception:
            pass
        self.destroy()

import threading

class RunWindow(tk.Toplevel):
    def __init__(self, master, cfg: ConfigManager, styles: StyleManager, llm: LLMClient, input_text: str):
        super().__init__(master)
        self.cfg = cfg
        self.styles = styles
        self.llm = llm
        self._initial_text = input_text
        self.title(t("run.window.title"))
        self.geometry("800x450")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        top = ttk.Frame(self); top.pack(side="top", fill="x", padx=8, pady=6)
        self.choose_style_label = ttk.Label(top, text=t("run.choose_style"))
        self.choose_style_label.pack(side="left")
        self.style_var = tk.StringVar(value=self.cfg.get("default_style", "Python"))
        self.style_box = ttk.Combobox(top, textvariable=self.style_var, state="readonly", values=self.styles.names, width=20); self.style_box.pack(side="left", padx=6)
        self.run_btn = ttk.Button(top, text=t("run.run"), command=self.on_run); self.run_btn.pack(side="left", padx=6)
        self.copy_btn = ttk.Button(top, text=t("run.copy"), command=self.on_copy); self.copy_btn.pack(side="left", padx=6)
        self.save_btn = ttk.Button(top, text=t("run.save_log"), command=self.on_save_log); self.save_btn.pack(side="left", padx=6)
        self.close_btn = ttk.Button(top, text=t("run.close"), command=self.on_close); self.close_btn.pack(side="right")

        self.status_var = tk.StringVar(value=t("run.ready"))
        ttk.Label(self, textvariable=self.status_var, anchor="w").pack(side="bottom", fill="x", padx=8, pady=4)

        self.output = tk.Text(self, wrap="word", height=20, background="#111", foreground="#EEE", insertbackground="#EEE")
        self.output.configure(font=("TkFixedFont", max(10, int(master.font_size))))
        self.output.pack(fill="both", expand=True, padx=8, pady=(0,8))

        self.refresh_styles()
        register_listener(self.on_lang_changed)

    def refresh_styles(self):
        values = self.styles.names
        self.style_box["values"] = values
        current = self.style_var.get()
        if current not in values:
            fallback = self.cfg.get("default_style", "")
            if fallback not in values:
                fallback = values[0] if values else ""
            self.style_var.set(fallback)

    def on_lang_changed(self, lang: str):
        self.title(t("run.window.title"))
        self.refresh_styles()
        self.choose_style_label.configure(text=t("run.choose_style"))
        self.run_btn.configure(text=t("run.run"))
        self.copy_btn.configure(text=t("run.copy"))
        self.save_btn.configure(text=t("run.save_log"))
        self.close_btn.configure(text=t("run.close"))
        if self.output.get("1.0", "end-1c").strip() == "":
            self.status_var.set(t("run.no_output"))
        else:
            self.status_var.set(t("run.ready"))

    def on_run(self):
        style = self.style_var.get()
        if hasattr(self.master, "text"):
            current_text = self.master.text.get("1.0", "end-1c")
        else:
            current_text = self._initial_text
        if not (current_text or "").strip():
            messagebox.showwarning(APP_NAME, t("warn.no_text")); return
        if not style:
            messagebox.showwarning(APP_NAME, t("warn.no_style")); return
        self.status_var.set(t("run.running"))
        self.run_btn.configure(state="disabled")
        self.output.delete("1.0", "end")
        threading.Thread(target=self._do_run, args=(style, current_text), daemon=True).start()

    def _do_run(self, style: str, text: str):
        try:
            result = self.llm.generate_compiler_output(style, text)
            self.after(0, self._update_output, result, None)
        except Exception as e:
            self.after(0, self._update_output, "", str(e))

    def _update_output(self, text: str, err: Optional[str]):
        if err:
            messagebox.showerror(APP_NAME, t("msg.llm_failed", err=err))
            self.status_var.set(t("run.ready"))
        else:
            self.output.insert("1.0", text)
            if (text or "").strip() == "":
                self.status_var.set(t("run.no_output"))
            else:
                self.status_var.set(t("run.ready"))
        self.run_btn.configure(state="normal")

    def on_copy(self):
        try:
            content = self.output.get("1.0", "end-1c")
            self.clipboard_clear(); self.clipboard_append(content)
            messagebox.showinfo(APP_NAME, t("warn.copy_ok"))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("warn.copy_failed", err=str(e)))

    def on_save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log", "*.log"), ("Text", "*.txt"), ("All", "*.*")])
        if not path: return
        try:
            write_text_utf8(path, self.output.get("1.0", "end-1c"))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("warn.save_log_failed", err=str(e)))

    def on_close(self):
        try:
            unregister_listener(self.on_lang_changed)
        except Exception:
            pass
        self.destroy()

class LLMSettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg: ConfigManager, llm: LLMClient):
        super().__init__(master)
        self.cfg = cfg; self.llm = llm
        self.title(t("llm.title")); self.resizable(False, False)
        pad = {"padx":8, "pady":4}; frm = ttk.Frame(self); frm.pack(fill="both", expand=True, **pad)

        self.base_url = tk.StringVar(value=cfg.get_nested("llm", "base_url") or "")
        self.model = tk.StringVar(value=cfg.get_nested("llm", "model") or "")
        self.api_key = tk.StringVar(value=cfg.get_nested("llm", "api_key") or "")
        self.header_name = tk.StringVar(value=cfg.get_nested("llm", "auth", "header_name") or "")
        self.header_prefix = tk.StringVar(value=cfg.get_nested("llm", "auth", "prefix") or "")
        self.temperature = tk.DoubleVar(value=self._safe_float(cfg.get_nested("llm", "temperature"), 0.1))
        self.max_tokens = tk.IntVar(value=self._safe_int(cfg.get_nested("llm", "max_tokens"), 900))
        self.timeout = tk.IntVar(value=self._safe_int(cfg.get_nested("llm", "timeout_seconds"), 60))

        row=0
        self.lbl_base=ttk.Label(frm,text=t("llm.base_url")); self.lbl_base.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.base_url,width=50).grid(row=row,column=1,**pad); row+=1
        self.lbl_model=ttk.Label(frm,text=t("llm.model")); self.lbl_model.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.model,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_key=ttk.Label(frm,text=t("llm.api_key")); self.lbl_key.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.api_key,width=50,show="*").grid(row=row,column=1,**pad); row+=1
        self.lbl_hname=ttk.Label(frm,text=t("llm.header_name")); self.lbl_hname.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.header_name,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_hprefix=ttk.Label(frm,text=t("llm.header_prefix")); self.lbl_hprefix.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.header_prefix,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_temp=ttk.Label(frm,text=t("llm.temperature")); self.lbl_temp.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.temperature,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_max=ttk.Label(frm,text=t("llm.max_tokens")); self.lbl_max.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.max_tokens,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_timeout=ttk.Label(frm,text=t("llm.timeout")); self.lbl_timeout.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.timeout,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1

        self.security_note = ttk.Label(frm, text=t("llm.security_note"), foreground="red", wraplength=420)
        self.security_note.grid(row=row, column=0, columnspan=2, sticky="w", **pad); row+=1

        btns = ttk.Frame(frm); btns.grid(row=row, column=0, columnspan=2, sticky="e", **pad)
        self.btn_save=ttk.Button(btns,text=t("styles.save"),command=self.on_save); self.btn_save.pack(side="right",padx=4)
        self.btn_test=ttk.Button(btns,text=t("settings.test_llm"),command=self.on_test); self.btn_test.pack(side="right",padx=4)
        self.btn_close=ttk.Button(btns,text=t("styles.close"),command=self.destroy); self.btn_close.pack(side="right",padx=4)

        register_listener(self.on_lang_changed)

    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _build_llm_overrides(self):
        try:
            temperature = float(self.temperature.get())
            max_tokens = int(self.max_tokens.get())
            timeout = int(self.timeout.get())
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(e)))
            return None
        return {
            "llm": {
                "base_url": self.base_url.get().strip(),
                "model": self.model.get().strip(),
                "api_key": self.api_key.get().strip(),
                "auth": {
                    "header_name": self.header_name.get().strip(),
                    "prefix": self.header_prefix.get(),
                },
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout_seconds": timeout,
            }
        }

    def on_lang_changed(self, lang: str):
        self.title(t("llm.title"))
        self.lbl_base.configure(text=t("llm.base_url"))
        self.lbl_model.configure(text=t("llm.model"))
        self.lbl_key.configure(text=t("llm.api_key"))
        self.lbl_hname.configure(text=t("llm.header_name"))
        self.lbl_hprefix.configure(text=t("llm.header_prefix"))
        self.lbl_temp.configure(text=t("llm.temperature"))
        self.lbl_max.configure(text=t("llm.max_tokens"))
        self.lbl_timeout.configure(text=t("llm.timeout"))
        self.security_note.configure(text=t("llm.security_note"))
        self.btn_save.configure(text=t("styles.save"))
        self.btn_test.configure(text=t("settings.test_llm"))
        self.btn_close.configure(text=t("styles.close"))

    def on_save(self):
        try:
            self.cfg.set_nested("llm","base_url",self.base_url.get().strip())
            self.cfg.set_nested("llm","model",self.model.get().strip())
            self.cfg.set_nested("llm","api_key",self.api_key.get().strip())
            self.cfg.set_nested("llm","auth","header_name",self.header_name.get().strip())
            self.cfg.set_nested("llm","auth","prefix",self.header_prefix.get())
            self.cfg.set_nested("llm","temperature",float(self.temperature.get()))
            self.cfg.set_nested("llm","max_tokens",int(self.max_tokens.get()))
            self.cfg.set_nested("llm","timeout_seconds",int(self.timeout.get()))
            messagebox.showinfo(APP_NAME, t("msg.config_saved"))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(e)))

    def on_test(self):
        if getattr(self, "_testing", False):
            return
        overrides = self._build_llm_overrides()
        if overrides is None:
            return
        self._testing = True
        self.btn_test.configure(state="disabled")
        threading.Thread(target=self._do_test, args=(overrides,), daemon=True).start()

    def _do_test(self, overrides):
        try:
            ok, msg = self.llm.test_connectivity(overrides=overrides)
        except Exception as e:
            ok, msg = False, str(e)
        self.after(0, lambda: self._finish_test(ok, msg))

    def _finish_test(self, ok: bool, msg: str):
        self._testing = False
        self.btn_test.configure(state="normal")
        if ok: messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else: messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=msg))

    def destroy(self):
        try: unregister_listener(self.on_lang_changed)
        except Exception: pass
        super().destroy()

class StylesDialog(tk.Toplevel):
    def __init__(self, master, styles: StyleManager, cfg: ConfigManager, on_changed=None):
        super().__init__(master)
        self.styles = styles; self.cfg = cfg; self._on_changed = on_changed
        self.title(t("styles.title")); self.geometry("700x500")

        container = ttk.Frame(self); container.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(container); right = ttk.Frame(container)
        left.pack(side="left", fill="y"); right.pack(side="right", fill="both", expand=True)

        self.listbox = tk.Listbox(left, height=20); self.listbox.pack(side="top", fill="y", padx=4, pady=4)
        for n in self.styles.names: self.listbox.insert("end", n)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btns = ttk.Frame(left); btns.pack(side="top", pady=6)
        ttk.Button(btns, text=t("styles.add"), command=self.on_add).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text=t("styles.edit"), command=self.on_edit).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text=t("styles.delete"), command=self.on_delete).grid(row=0, column=2, padx=4)
        ttk.Button(btns, text=t("styles.close"), command=self.destroy).grid(row=0, column=3, padx=4)

        self.name_var = tk.StringVar()
        self.template = tk.Text(right, wrap="word")
        self.hint = ttk.Label(right, text=t("styles.example_hint"))
        self.lbl_name = ttk.Label(right, text=t("styles.name")); self.lbl_name.pack(anchor="w")
        ttk.Entry(right, textvariable=self.name_var, width=40).pack(fill="x", padx=2, pady=2)
        self.lbl_template = ttk.Label(right, text=t("styles.template")); self.lbl_template.pack(anchor="w")
        self.template.pack(fill="both", expand=True, padx=2, pady=2)

        self.save_btn = ttk.Button(right, text=t("styles.save"), command=self.on_save); self.save_btn.pack(anchor="e", pady=4)
        self.hint.pack(anchor="w")

        register_listener(self.on_lang_changed)

    def on_lang_changed(self, lang: str):
        self.title(t("styles.title"))
        self.hint.configure(text=t("styles.example_hint"))
        self.lbl_name.configure(text=t("styles.name"))
        self.lbl_template.configure(text=t("styles.template"))
        self.save_btn.configure(text=t("styles.save"))

    def on_select(self, evt=None):
        sel = self._selected_name()
        if not sel: return
        self.name_var.set(sel)
        self.template.delete("1.0","end")
        self.template.insert("1.0", self.styles.get(sel))

    def on_add(self):
        self.name_var.set("NewStyle")
        self.template.delete("1.0","end")
        self.template.insert("1.0", "STRICT compiler-style diagnostics for ENGLISH text; success => __TC_OK__\nINPUT:\n{input_text}")

    def on_edit(self):
        name = self._selected_name()
        if not name:
            messagebox.showwarning(APP_NAME, t("warn.no_style"))
            return
        self.name_var.set(name)
        self.template.delete("1.0","end")
        self.template.insert("1.0", self.styles.get(name))
        self.template.focus_set()

    def on_delete(self):
        name = self._selected_name()
        if not name: return
        if name in BUILTIN_STYLES:
            data = self.cfg.get("styles", {}) or {}
            if not isinstance(data, dict):
                data = {}
            if name in data:
                del data[name]; self.cfg.set("styles", data)
        else:
            self.styles.delete(name)
        self.refresh_list()
        self._notify_styles_changed()

    def on_save(self):
        name = (self.name_var.get() or "").strip()
        if not name: return
        template = self.template.get("1.0","end-1c")
        self.styles.set(name, template)
        self.refresh_list()
        self._notify_styles_changed()

    def refresh_list(self):
        self.styles.reload()
        self.listbox.delete(0,"end")
        for n in self.styles.names: self.listbox.insert("end", n)

    def _notify_styles_changed(self):
        if self._on_changed:
            try:
                self._on_changed()
            except Exception:
                pass

    def _selected_name(self) -> Optional[str]:
        sel = self.listbox.curselection()
        if not sel: return None
        return self.listbox.get(sel[0])

    def destroy(self):
        try: unregister_listener(self.on_lang_changed)
        except Exception: pass
        super().destroy()

def main():
    app = TypoCompilerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
