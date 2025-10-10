
# typocompiler.py
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional

from config_manager import ConfigManager
from i18n import t, set_language, get_language, register_listener, unregister_listener
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
        set_language(self.cfg.get("language", "zh"))
        self.styles = StyleManager(self.cfg)
        self.llm = LLMClient(self.cfg, self.styles)

        self.current_file: Optional[str] = None
        self.font_size = int(self.cfg.get("font_size", 12))

        self.create_widgets()
        self.apply_font_size()
        self.update_title()
        self.status_var.set(t("status.ready"))

        register_listener(self.on_lang_changed)

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
        self.lang_var = tk.StringVar(value=self.cfg.get("language", "zh"))
        self.lang_menu.add_radiobutton(label=t("settings.lang.zh"), value="zh", variable=self.lang_var, command=self.change_language)
        self.lang_menu.add_radiobutton(label=t("settings.lang.en"), value="en", variable=self.lang_var, command=self.change_language)
        self.settings_menu.add_cascade(label=t("settings.language"), menu=self.lang_menu)

        self.style_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.default_style_var = tk.StringVar(value=self.cfg.get("default_style", "Python"))
        for name in self.styles.names:
            self.style_menu.add_radiobutton(label=name, value=name, variable=self.default_style_var, command=self.on_default_style_changed)
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

        # 状态栏
        self.status_var = tk.StringVar(value="")
        self.status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(side="bottom", fill="x")

    def on_lang_changed(self, lang: str):
        self.title(t("app.title"))
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
        self.lang_menu.add_radiobutton(label=t("settings.lang.zh"), value="zh", variable=self.lang_var, command=self.change_language)
        self.lang_menu.add_radiobutton(label=t("settings.lang.en"), value="en", variable=self.lang_var, command=self.change_language)
        self.settings_menu.add_cascade(label=t("settings.language"), menu=self.lang_menu)

        self.style_menu = tk.Menu(self.settings_menu, tearoff=0)
        for name in self.styles.names:
            self.style_menu.add_radiobutton(label=name, value=name, variable=self.default_style_var, command=self.on_default_style_changed)
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

        if self.current_file:
            self.status_var.set(t("status.loaded", name=os.path.basename(self.current_file)))
        else:
            self.status_var.set(t("status.ready"))

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

    def on_default_style_changed(self):
        style = self.default_style_var.get()
        self.cfg.set("default_style", style)

    def open_manage_styles(self):
        StylesDialog(self, self.styles, self.cfg)

    def open_llm_settings(self):
        LLMSettingsDialog(self, self.cfg, self.llm)

    def test_llm(self):
        ok, msg = self.llm.test_connectivity()
        if ok:
            messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=msg))

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
        self.title(base)

    def new_file(self):
        self.text.delete("1.0", "end")
        self.current_file = None
        self.update_title()
        self.status_var.set(t("status.ready"))

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not path:
            return
        self.open_file_from_path(path)

    def open_file_from_path(self, path: str):
        try:
            content = read_text_utf8(path)
            self.text.delete("1.0", "end")
            self.text.insert("1.0", content)
            self.current_file = path
            self.cfg.add_recent_file(path)
            self.refresh_recent_files_menu()
            self.update_title()
            self.status_var.set(t("status.loaded", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.open_failed", err=str(e)))

    def save_file(self):
        if not self.current_file:
            return self.save_file_as()
        try:
            write_text_utf8(self.current_file, self.text.get("1.0", "end-1c"))
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
            self.update_title()
            self.status_var.set(t("status.saved", name=os.path.basename(path)))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.save_failed", err=str(e)))

    def open_run_window(self):
        RunWindow(self, self.cfg, self.styles, self.llm, self.text.get("1.0", "end-1c"))

    def on_close(self):
        try:
            unregister_listener(self.on_lang_changed)
        except Exception:
            pass
        self.destroy()

# --- Run Window & Settings/Styles dialogs ---
import threading

class RunWindow(tk.Toplevel):
    def __init__(self, master, cfg: ConfigManager, styles: StyleManager, llm: LLMClient, input_text: str):
        super().__init__(master)
        self.cfg = cfg
        self.styles = styles
        self.llm = llm
        self.input_text = input_text
        self.title(t("run.window.title"))
        self.geometry("800x450")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        top = ttk.Frame(self); top.pack(side="top", fill="x", padx=8, pady=6)
        ttk.Label(top, text=t("run.choose_style")).pack(side="left")
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

        register_listener(self.on_lang_changed)

    def on_lang_changed(self, lang: str):
        self.title(t("run.window.title"))
        self.style_box["values"] = self.styles.names
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
        if not self.input_text.strip():
            messagebox.showwarning(APP_NAME, t("warn.no_text")); return
        if not style:
            messagebox.showwarning(APP_NAME, t("warn.no_style")); return
        self.status_var.set(t("run.running"))
        self.run_btn.configure(state="disabled")
        self.output.delete("1.0", "end")
        threading.Thread(target=self._do_run, args=(style, self.input_text), daemon=True).start()

    def _do_run(self, style: str, text: str):
        try:
            result = self.llm.generate_compiler_output(style, text)
            self.after(0, self._update_output, result, None)
        except Exception as e:
            self.after(0, self._update_output, "", str(e))

    def _update_output(self, text: str, err: Optional[str]):
        if err:
            messagebox.showerror(APP_NAME, t("msg.llm_failed", err=err))
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

        self.base_url = tk.StringVar(value=cfg.get_nested("llm", "base_url"))
        self.model = tk.StringVar(value=cfg.get_nested("llm", "model"))
        self.api_key = tk.StringVar(value=cfg.get_nested("llm", "api_key"))
        self.header_name = tk.StringVar(value=cfg.get_nested("llm", "auth", "header_name"))
        self.header_prefix = tk.StringVar(value=cfg.get_nested("llm", "auth", "prefix"))
        self.temperature = tk.DoubleVar(value=float(cfg.get_nested("llm", "temperature")))
        self.max_tokens = tk.IntVar(value=int(cfg.get_nested("llm", "max_tokens")))
        self.timeout = tk.IntVar(value=int(cfg.get_nested("llm", "timeout_seconds")))

        row=0
        self.lbl_base=ttk.Label(frm,text=t("llm.base_url")); self.lbl_base.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.base_url,width=50).grid(row=row,column=1,**pad); row+=1
        self.lbl_model=ttk.Label(frm,text=t("llm.model")); self.lbl_model.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.model,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_key=ttk.Label(frm,text=t("llm.api_key")); self.lbl_key.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.api_key,width=50,show="*").grid(row=row,column=1,**pad); row+=1
        self.lbl_hname=ttk.Label(frm,text=t("llm.header_name")); self.lbl_hname.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.header_name,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_hprefix=ttk.Label(frm,text=t("llm.header_prefix")); self.lbl_hprefix.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.header_prefix,width=30).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_temp=ttk.Label(frm,text=t("llm.temperature")); self.lbl_temp.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.temperature,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_max=ttk.Label(frm,text=t("llm.max_tokens")); self.lbl_max.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.max_tokens,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1
        self.lbl_timeout=ttk.Label(frm,text=t("llm.timeout")); self.lbl_timeout.grid(row=row,column=0,sticky="e",**pad); ttk.Entry(frm,textvariable=self.timeout,width=10).grid(row=row,column=1,sticky="w",**pad); row+=1

        btns = ttk.Frame(frm); btns.grid(row=row, column=0, columnspan=2, sticky="e", **pad)
        self.btn_save=ttk.Button(btns,text=t("styles.save"),command=self.on_save); self.btn_save.pack(side="right",padx=4)
        self.btn_test=ttk.Button(btns,text=t("settings.test_llm"),command=self.on_test); self.btn_test.pack(side="right",padx=4)
        self.btn_close=ttk.Button(btns,text=t("styles.close"),command=self.destroy); self.btn_close.pack(side="right",padx=4)

        register_listener(self.on_lang_changed)

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
        ok, msg = self.llm.test_connectivity()
        if ok: messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else: messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=msg))

    def destroy(self):
        try: unregister_listener(self.on_lang_changed)
        except Exception: pass
        super().destroy()

class StylesDialog(tk.Toplevel):
    def __init__(self, master, styles: StyleManager, cfg: ConfigManager):
        super().__init__(master)
        self.styles = styles; self.cfg = cfg
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
        self.template.insert("1.0", "STRICT compiler-style diagnostics for ENGLISH text; success => __TC_OK__.\nINPUT:\n{input_text}")

    def on_edit(self):
        pass

    def on_delete(self):
        name = self._selected_name()
        if not name: return
        if name in BUILTIN_STYLES:
            data = self.cfg.get("styles", {}) or {}
            if name in data:
                del data[name]; self.cfg.set("styles", data)
            self.styles = StyleManager(self.cfg)
        else:
            self.styles.delete(name)
        self.refresh_list()

    def on_save(self):
        name = (self.name_var.get() or "").strip()
        if not name: return
        template = self.template.get("1.0","end-1c")
        self.styles.set(name, template)
        self.refresh_list()

    def refresh_list(self):
        self.styles = StyleManager(self.cfg)
        self.listbox.delete(0,"end")
        for n in self.styles.names: self.listbox.insert("end", n)

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
