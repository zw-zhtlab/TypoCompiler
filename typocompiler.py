"""Tkinter desktop interface for TypoCompiler."""

from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from config_manager import ConfigManager
from diagnostics import CompileResult, Diagnostic, render_diagnostics
from file_ops import TextDocument, read_document, write_document, write_text_utf8
from i18n import (
    get_language,
    get_supported_languages,
    register_listener,
    set_language,
    t,
    unregister_listener,
)
from llm_client import AnalysisRequest, LLMClient, RequestSnapshot
from styles import BUILTIN_STYLES, StyleManager

APP_NAME = "TypoCompiler"
WORKER_POLL_MS = 40


@dataclass(frozen=True, slots=True)
class _WorkerEvent:
    kind: str
    generation: int
    payload: tuple[object, ...]


def _fitted_geometry(
    widget: tk.Misc,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
) -> str:
    """Fit and center a window using Tk's DPI-aware logical screen dimensions."""

    screen_width = widget.winfo_screenwidth()
    screen_height = widget.winfo_screenheight()
    width = min(preferred_width, max(minimum_width, screen_width - 80))
    height = min(preferred_height, max(minimum_height, screen_height - 120))
    left = max(0, (screen_width - width) // 2)
    top = max(0, (screen_height - height) // 3)
    return f"{width}x{height}+{left}+{top}"


class TypoCompilerApp(tk.Tk):
    """A single-window editing and diagnostics workspace."""

    def __init__(self) -> None:
        super().__init__()
        self.minsize(760, 520)
        self.geometry(_fitted_geometry(self, 1100, 720, 760, 520))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.cfg = ConfigManager()
        raw_language = self.cfg.get("language", "zh")
        set_language(raw_language)
        if get_language() != raw_language:
            try:
                self.cfg.set("language", get_language())
            except (OSError, UnicodeError, TypeError, ValueError):
                pass

        self.styles = StyleManager(self.cfg)
        self.llm = LLMClient(self.cfg, self.styles)
        self.current_file: Optional[str] = None
        self.current_document = TextDocument("")
        self.font_size = self._normalize_font_size(self.cfg.get("font_size", 12))
        self.dirty = False

        self.lang_var = tk.StringVar(value=get_language())
        default_style = self.cfg.get("default_style", "Python")
        if default_style not in self.styles.names:
            default_style = self.styles.names[0]
            try:
                self.cfg.set("default_style", default_style)
            except (OSError, ValueError):
                pass
        self.default_style_var = tk.StringVar(value=default_style)
        self.status_var = tk.StringVar()
        self.position_var = tk.StringVar()
        self._generation = 0
        self._test_generation = 0
        self._running = False
        self._closing = False
        self._worker_results: queue.Queue[_WorkerEvent] = queue.Queue()
        self._worker_poll_id: str | None = None
        self._last_result: CompileResult | None = None
        self._last_source = ""
        self._result_stale = False

        self.create_widgets()
        self.bind_shortcuts()
        self.apply_font_size()
        self.set_clean_state()
        self.update_title()
        self._set_ready_status()
        self.update_cursor_status()
        self._schedule_worker_poll()
        self.text.focus_set()

        register_listener(self.on_lang_changed)
        if self.cfg.consume_reset_notice():
            messagebox.showinfo(APP_NAME, t("info.reset_defaults"))

    @staticmethod
    def _normalize_font_size(value: object) -> int:
        try:
            size = int(value)
        except (TypeError, ValueError):
            size = 12
        return max(8, min(40, size))

    def create_widgets(self) -> None:
        self._build_menus()

        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(side="top", fill="x")
        self.choose_style_label = ttk.Label(toolbar, text=t("run.choose_style"))
        self.choose_style_label.pack(side="left")
        self.style_box = ttk.Combobox(
            toolbar,
            textvariable=self.default_style_var,
            values=self.styles.names,
            state="readonly",
            width=18,
            takefocus=True,
        )
        self.style_box.pack(side="left", padx=(6, 12))
        self.style_box.bind("<<ComboboxSelected>>", self.on_default_style_changed)

        self.run_btn = ttk.Button(
            toolbar, text=t("run.run"), command=self.run_analysis, takefocus=True
        )
        self.run_btn.pack(side="left", padx=3)
        self.cancel_btn = ttk.Button(
            toolbar,
            text=t("run.cancel"),
            command=self.cancel_analysis,
            state="disabled",
            takefocus=True,
        )
        self.cancel_btn.pack(side="left", padx=3)
        self.copy_btn = ttk.Button(
            toolbar, text=t("run.copy"), command=self.copy_output, takefocus=True
        )
        self.copy_btn.pack(side="left", padx=(12, 3))
        self.save_log_btn = ttk.Button(
            toolbar, text=t("run.save_log"), command=self.save_log, takefocus=True
        )
        self.save_log_btn.pack(side="left", padx=3)

        self.workspace = ttk.PanedWindow(self, orient="vertical")
        self.workspace.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self.input_frame = ttk.LabelFrame(
            self.workspace, text=t("workspace.input"), padding=5
        )
        self.input_frame.rowconfigure(0, weight=1)
        self.input_frame.columnconfigure(0, weight=1)
        self.text = tk.Text(
            self.input_frame,
            wrap="none",
            undo=True,
            maxundo=2000,
            tabs=("4c",),
            takefocus=True,
        )
        input_y = ttk.Scrollbar(
            self.input_frame, orient="vertical", command=self.text.yview
        )
        input_x = ttk.Scrollbar(
            self.input_frame, orient="horizontal", command=self.text.xview
        )
        self.text.configure(yscrollcommand=input_y.set, xscrollcommand=input_x.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        input_y.grid(row=0, column=1, sticky="ns")
        input_x.grid(row=1, column=0, sticky="ew")
        self.text.bind("<<Modified>>", self.on_text_modified)
        self.text.bind("<KeyRelease>", self.update_cursor_status)
        self.text.bind("<ButtonRelease-1>", self.update_cursor_status)
        self.workspace.add(self.input_frame, weight=3)

        results = ttk.PanedWindow(self.workspace, orient="horizontal")
        self.issues_frame = ttk.LabelFrame(
            results, text=t("workspace.issues"), padding=5
        )
        self.issues_frame.rowconfigure(0, weight=1)
        self.issues_frame.columnconfigure(0, weight=1)
        self.issues = ttk.Treeview(
            self.issues_frame,
            columns=("line", "severity", "message"),
            show="headings",
            selectmode="browse",
            takefocus=True,
        )
        self.issues.column("line", width=62, stretch=False, anchor="center")
        self.issues.column("severity", width=88, stretch=False)
        self.issues.column("message", width=300, stretch=True)
        issues_scroll = ttk.Scrollbar(
            self.issues_frame, orient="vertical", command=self.issues.yview
        )
        self.issues.configure(yscrollcommand=issues_scroll.set)
        self.issues.grid(row=0, column=0, sticky="nsew")
        issues_scroll.grid(row=0, column=1, sticky="ns")
        self.issues.bind("<Double-1>", self.jump_to_selected_diagnostic)
        self.issues.bind("<Return>", self.jump_to_selected_diagnostic)
        results.add(self.issues_frame, weight=2)

        self.output_frame = ttk.LabelFrame(
            results, text=t("run.window.title"), padding=5
        )
        self.output_frame.rowconfigure(0, weight=1)
        self.output_frame.columnconfigure(0, weight=1)
        self.output = tk.Text(
            self.output_frame,
            wrap="none",
            state="disabled",
            background="#171717",
            foreground="#f2f2f2",
            selectbackground="#365f91",
            takefocus=True,
        )
        output_y = ttk.Scrollbar(
            self.output_frame, orient="vertical", command=self.output.yview
        )
        output_x = ttk.Scrollbar(
            self.output_frame, orient="horizontal", command=self.output.xview
        )
        self.output.configure(yscrollcommand=output_y.set, xscrollcommand=output_x.set)
        self.output.grid(row=0, column=0, sticky="nsew")
        output_y.grid(row=0, column=1, sticky="ns")
        output_x.grid(row=1, column=0, sticky="ew")
        results.add(self.output_frame, weight=3)
        self.workspace.add(results, weight=2)

        status = ttk.Frame(self, padding=(8, 3))
        status.pack(side="bottom", fill="x")
        self.status = ttk.Label(status, textvariable=self.status_var, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        ttk.Separator(status, orient="vertical").pack(side="left", fill="y", padx=8)
        self.position = ttk.Label(status, textvariable=self.position_var, anchor="e")
        self.position.pack(side="right")

        for name, colors in {
            "diagnostic_error": ("#7f1d1d", "#ffffff"),
            "diagnostic_warning": ("#7c4a03", "#ffffff"),
            "diagnostic_info": ("#174a6e", "#ffffff"),
            "diagnostic_hint": ("#3f3f46", "#ffffff"),
        }.items():
            self.text.tag_configure(
                name, background=colors[0], foreground=colors[1], underline=True
            )
        self._update_tree_headings()
        self._set_output(t("workspace.output_empty"))

    def _build_menus(self) -> None:
        previous = getattr(self, "menubar", None)
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(
            label=t("file.new"), accelerator="Ctrl+N", command=self.new_file
        )
        self.file_menu.add_command(
            label=t("file.open"), accelerator="Ctrl+O", command=self.open_file
        )
        self.file_menu.add_command(
            label=t("file.save"), accelerator="Ctrl+S", command=self.save_file
        )
        self.file_menu.add_command(
            label=t("file.save_as"),
            accelerator="Ctrl+Shift+S",
            command=self.save_file_as,
        )
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label=t("file.recent"), menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=t("file.exit"), command=self.on_close)
        self.menubar.add_cascade(label=t("menu.file"), menu=self.file_menu)

        edit_menu = tk.Menu(self.menubar, tearoff=0)
        edit_menu.add_command(
            label=t("edit.undo"),
            accelerator="Ctrl+Z",
            command=lambda: self._edit_event("<<Undo>>"),
        )
        edit_menu.add_command(
            label=t("edit.redo"),
            accelerator="Ctrl+Y",
            command=lambda: self._edit_event("<<Redo>>"),
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label=t("edit.cut"),
            accelerator="Ctrl+X",
            command=lambda: self._edit_event("<<Cut>>"),
        )
        edit_menu.add_command(
            label=t("edit.copy"),
            accelerator="Ctrl+C",
            command=lambda: self._edit_event("<<Copy>>"),
        )
        edit_menu.add_command(
            label=t("edit.paste"),
            accelerator="Ctrl+V",
            command=lambda: self._edit_event("<<Paste>>"),
        )
        edit_menu.add_command(
            label=t("edit.select_all"),
            accelerator="Ctrl+A",
            command=self.select_all,
        )
        self.menubar.add_cascade(label=t("menu.edit"), menu=edit_menu)

        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.rebuild_language_menu()
        self.settings_menu.add_cascade(
            label=t("settings.language"), menu=self.lang_menu
        )
        self.style_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.rebuild_style_menu()
        self.settings_menu.add_cascade(
            label=t("settings.default_style"), menu=self.style_menu
        )
        self.settings_menu.add_command(
            label=t("settings.manage_styles"), command=self.open_manage_styles
        )
        self.settings_menu.add_separator()
        self.settings_menu.add_command(
            label=t("settings.llm"), command=self.open_llm_settings
        )
        self.settings_menu.add_command(
            label=t("settings.test_llm"), command=self.test_llm
        )
        self.settings_menu.add_separator()
        font_menu = tk.Menu(self.settings_menu, tearoff=0)
        font_menu.add_command(
            label=t("settings.font.inc"),
            accelerator="Ctrl++",
            command=lambda: self.adjust_font(1),
        )
        font_menu.add_command(
            label=t("settings.font.dec"),
            accelerator="Ctrl+-",
            command=lambda: self.adjust_font(-1),
        )
        font_menu.add_command(
            label=t("settings.font.reset"),
            accelerator="Ctrl+0",
            command=self.reset_font,
        )
        self.settings_menu.add_cascade(label=t("settings.font"), menu=font_menu)
        self.menubar.add_cascade(label=t("menu.settings"), menu=self.settings_menu)

        run_menu = tk.Menu(self.menubar, tearoff=0)
        run_menu.add_command(
            label=t("run.run"), accelerator="F5", command=self.run_analysis
        )
        run_menu.add_command(
            label=t("run.cancel"), accelerator="Esc", command=self.cancel_analysis
        )
        run_menu.add_separator()
        run_menu.add_command(
            label=t("run.copy"),
            accelerator="Ctrl+Shift+C",
            command=self.copy_output,
        )
        run_menu.add_command(label=t("run.save_log"), command=self.save_log)
        self.menubar.add_cascade(label=t("menu.run"), menu=run_menu)
        self.refresh_recent_files_menu()

        if previous is not None:
            previous.destroy()

    def bind_shortcuts(self) -> None:
        bindings = {
            "<Control-n>": self.new_file,
            "<Control-o>": self.open_file,
            "<Control-s>": self.save_file,
            "<Control-Shift-S>": self.save_file_as,
            "<F5>": self.run_analysis,
            "<Escape>": self.cancel_analysis,
            "<Control-plus>": lambda: self.adjust_font(1),
            "<Control-equal>": lambda: self.adjust_font(1),
            "<Control-minus>": lambda: self.adjust_font(-1),
            "<Control-Key-0>": self.reset_font,
            "<Control-Shift-C>": self.copy_output,
        }
        for sequence, command in bindings.items():
            self.bind_all(
                sequence,
                lambda _event, callback=command: self._invoke_shortcut(callback),
            )

    @staticmethod
    def _invoke_shortcut(command):
        command()
        return "break"

    def _edit_event(self, sequence: str) -> None:
        widget = self.focus_get()
        if isinstance(widget, (tk.Text, tk.Entry, ttk.Entry)):
            widget.event_generate(sequence)

    def select_all(self) -> None:
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("insert")
        elif isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.selection_range(0, "end")

    def on_lang_changed(self, _language: str) -> None:
        self.lang_var.set(get_language())
        self._build_menus()
        self.choose_style_label.configure(text=t("run.choose_style"))
        self.run_btn.configure(text=t("run.run"))
        self.cancel_btn.configure(text=t("run.cancel"))
        self.copy_btn.configure(text=t("run.copy"))
        self.save_log_btn.configure(text=t("run.save_log"))
        self.input_frame.configure(text=t("workspace.input"))
        self.issues_frame.configure(text=t("workspace.issues"))
        self.output_frame.configure(text=t("run.window.title"))
        self._update_tree_headings()
        self.update_title()
        self.update_cursor_status()
        if self._last_result is None:
            self._set_output(t("workspace.output_empty"))
        self._refresh_status_text()

    def _update_tree_headings(self) -> None:
        self.issues.heading("line", text=t("diagnostic.line"))
        self.issues.heading("severity", text=t("diagnostic.severity"))
        self.issues.heading("message", text=t("diagnostic.message"))

    def rebuild_language_menu(self) -> None:
        self.lang_menu.delete(0, "end")
        for code in get_supported_languages():
            self.lang_menu.add_radiobutton(
                label=t(f"settings.lang.{code}"),
                value=code,
                variable=self.lang_var,
                command=self.change_language,
            )

    def change_language(self) -> None:
        language = self.lang_var.get()
        previous = get_language()
        set_language(language)
        try:
            self.cfg.set("language", language)
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            set_language(previous)
            self.lang_var.set(previous)
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))

    def rebuild_style_menu(self) -> None:
        self.style_menu.delete(0, "end")
        for name in self.styles.names:
            self.style_menu.add_radiobutton(
                label=name,
                value=name,
                variable=self.default_style_var,
                command=self.on_default_style_changed,
            )

    def refresh_recent_files_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        recent = self.cfg.get("recent_files", [])
        if not recent:
            self.recent_menu.add_command(label=t("recent.empty"), state="disabled")
            return
        for path in recent:
            self.recent_menu.add_command(
                label=path,
                command=lambda selected=path: self.open_file_from_path(selected),
            )

    def on_default_style_changed(self, _event=None) -> None:
        style = self.default_style_var.get()
        try:
            self.cfg.set("default_style", style)
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            previous = self.cfg.get("default_style", "Python")
            if previous in self.styles.names:
                self.default_style_var.set(previous)
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))
            return
        if self._last_result is not None:
            self._render_last_result()

    def on_styles_changed(self) -> None:
        self.styles.reload()
        names = self.styles.names
        current = self.default_style_var.get()
        if current not in names:
            current = names[0]
            self.default_style_var.set(current)
            self.cfg.set("default_style", current)
        self.style_box.configure(values=names)
        self._build_menus()

    def open_manage_styles(self) -> None:
        StylesDialog(self, self.styles, self.cfg, on_changed=self.on_styles_changed)

    def open_llm_settings(self) -> None:
        LLMSettingsDialog(self, self.cfg, self.llm)

    def _schedule_worker_poll(self) -> None:
        if self._closing or self._worker_poll_id is not None:
            return
        self._worker_poll_id = self.after(WORKER_POLL_MS, self._poll_worker_results)

    def _poll_worker_results(self) -> None:
        self._worker_poll_id = None
        if self._closing:
            return
        self._drain_worker_results()
        self._schedule_worker_poll()

    def _drain_worker_results(self) -> None:
        for _item in range(100):
            try:
                event = self._worker_results.get_nowait()
            except queue.Empty:
                break
            self._handle_worker_event(event)

    def _handle_worker_event(self, event: _WorkerEvent) -> None:
        if self._closing:
            return
        if event.kind == "connectivity":
            if event.generation != self._test_generation:
                return
            ok, message = event.payload
            self._finish_test_llm(bool(ok), str(message))
            return
        if event.kind == "analysis":
            if event.generation != self._generation:
                return
            request, result, error = event.payload
            self._finish_analysis(
                event.generation,
                request,
                result,
                error,
            )

    def test_llm(self) -> None:
        if getattr(self, "_testing_llm", False):
            return
        try:
            snapshot = self.llm.prepare_connectivity()
        except Exception as error:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=str(error)))
            return
        self._testing_llm = True
        self._test_generation += 1
        request_id = self._test_generation
        self.status_var.set(t("status.testing_llm"))
        threading.Thread(
            target=self._do_test_llm,
            args=(request_id, snapshot),
            daemon=True,
        ).start()

    def _do_test_llm(self, request_id: int, snapshot: RequestSnapshot) -> None:
        try:
            ok, message = self.llm.run_connectivity(snapshot)
        except Exception as error:
            ok, message = False, str(error)
        self._worker_results.put(
            _WorkerEvent("connectivity", request_id, (ok, message))
        )

    def _finish_test_llm(self, ok: bool, message: str) -> None:
        self._testing_llm = False
        if ok:
            messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=message))
        self._refresh_status_text()

    def adjust_font(self, delta: int) -> None:
        previous = self.font_size
        self.font_size = max(8, min(40, previous + delta))
        self.apply_font_size()
        try:
            self.cfg.set("font_size", self.font_size)
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            self.font_size = previous
            self.apply_font_size()
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))

    def reset_font(self) -> None:
        previous = self.font_size
        self.font_size = 12
        self.apply_font_size()
        try:
            self.cfg.set("font_size", self.font_size)
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            self.font_size = previous
            self.apply_font_size()
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))

    def apply_font_size(self) -> None:
        font = ("TkFixedFont", self.font_size)
        self.text.configure(font=font)
        self.output.configure(font=font)

    def update_title(self) -> None:
        title = t("app.title")
        if self.current_file:
            title += f" — {os.path.basename(self.current_file)}"
        if self.dirty:
            title += " *"
        self.title(title)

    def set_clean_state(self) -> None:
        self.dirty = False
        self.text.edit_modified(False)

    def on_text_modified(self, _event=None) -> None:
        if not self.text.edit_modified():
            return
        self.dirty = True
        self.update_title()
        self.text.edit_modified(False)
        if self._last_result is not None and not self._result_stale:
            self._result_stale = True
            self._clear_highlights()
            self.status_var.set(t("status.results_stale"))
        self.update_cursor_status()

    def update_cursor_status(self, _event=None) -> None:
        line_text, column_text = self.text.index("insert").split(".")
        self.position_var.set(
            t(
                "status.cursor",
                line=int(line_text),
                column=int(column_text) + 1,
            )
        )

    def confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        decision = messagebox.askyesnocancel(APP_NAME, t("warn.unsaved"))
        if decision is None:
            return False
        if decision:
            return bool(self.save_file())
        return True

    def _set_ready_status(self) -> None:
        if self.current_file:
            self.status_var.set(
                t("status.loaded", name=os.path.basename(self.current_file))
            )
        else:
            self.status_var.set(t("status.ready"))

    def _refresh_status_text(self) -> None:
        if getattr(self, "_testing_llm", False):
            self.status_var.set(t("status.testing_llm"))
        elif self._running:
            self.status_var.set(t("run.running"))
        elif self._result_stale:
            self.status_var.set(t("status.results_stale"))
        elif self._last_result is not None:
            if self._last_result.clean:
                self.status_var.set(t("run.no_output"))
            else:
                self.status_var.set(
                    t("status.issue_count", count=len(self._last_result.diagnostics))
                )
        else:
            self._set_ready_status()

    def _invalidate_run(self) -> None:
        if self._running:
            self._generation += 1
            self._set_running(False)

    def _clear_results(self) -> None:
        self._invalidate_run()
        self._last_result = None
        self._last_source = ""
        self._result_stale = False
        self._clear_highlights()
        for item in self.issues.get_children():
            self.issues.delete(item)
        self._set_output(t("workspace.output_empty"))

    def new_file(self) -> None:
        if not self.confirm_discard():
            return
        self.text.delete("1.0", "end")
        self.current_file = None
        self.current_document = TextDocument("")
        self._clear_results()
        self.set_clean_state()
        self.update_title()
        self._set_ready_status()
        self.text.focus_set()

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                (t("filetype.text"), "*.txt"),
                (t("filetype.markdown"), "*.md"),
                (t("filetype.all"), "*.*"),
            ]
        )
        if path:
            self.open_file_from_path(path)

    def open_file_from_path(self, path: str) -> None:
        if not self.confirm_discard():
            return
        try:
            document = read_document(path)
        except (OSError, UnicodeError, ValueError) as error:
            if isinstance(error, FileNotFoundError):
                try:
                    self.cfg.remove_recent_file(path)
                    self.refresh_recent_files_menu()
                except (OSError, ValueError):
                    pass
            messagebox.showerror(APP_NAME, t("msg.open_failed", err=str(error)))
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", document.text)
        self.current_file = os.path.abspath(path)
        self.current_document = document
        self._remember_recent_file(self.current_file)
        self._clear_results()
        self.set_clean_state()
        self.update_title()
        self._set_ready_status()
        self.text.focus_set()

    def save_file(self) -> bool:
        if not self.current_file:
            return self.save_file_as()
        text = self.text.get("1.0", "end-1c")
        try:
            document = write_document(
                self.current_file, text, metadata=self.current_document
            )
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("msg.save_failed", err=str(error)))
            return False
        self.current_document = document
        self.set_clean_state()
        self.update_title()
        self.status_var.set(t("status.saved", name=os.path.basename(self.current_file)))
        return True

    def save_file_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                (t("filetype.text"), "*.txt"),
                (t("filetype.markdown"), "*.md"),
                (t("filetype.all"), "*.*"),
            ],
        )
        if not path:
            return False
        text = self.text.get("1.0", "end-1c")
        try:
            document = write_document(path, text, metadata=self.current_document)
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("msg.save_failed", err=str(error)))
            return False
        self.current_file = os.path.abspath(path)
        self.current_document = document
        self._remember_recent_file(self.current_file)
        self.set_clean_state()
        self.update_title()
        self.status_var.set(t("status.saved", name=os.path.basename(self.current_file)))
        return True

    def _remember_recent_file(self, path: str) -> None:
        """Keep recent-file persistence from breaking a successful file operation."""

        try:
            self.cfg.add_recent_file(path)
            self.refresh_recent_files_menu()
        except (OSError, UnicodeError, TypeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))

    def run_analysis(self) -> None:
        if self._running:
            return
        source = self.text.get("1.0", "end-1c")
        style = self.default_style_var.get()
        if not source.strip():
            messagebox.showwarning(APP_NAME, t("warn.no_text"))
            self.text.focus_set()
            return
        if not style:
            messagebox.showwarning(APP_NAME, t("warn.no_style"))
            return
        try:
            request = self.llm.prepare_analysis(style, source)
        except (TypeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("msg.llm_failed", err=str(error)))
            return

        self._generation += 1
        request_id = self._generation
        self._set_running(True)
        self.status_var.set(t("run.running"))
        threading.Thread(
            target=self._do_analysis,
            args=(request_id, request),
            daemon=True,
        ).start()

    def open_run_window(self) -> None:
        """Compatibility alias: running now stays in the main workspace."""
        self.run_analysis()

    def _do_analysis(self, request_id: int, request: AnalysisRequest) -> None:
        try:
            result = self.llm.run_analysis(request)
            error = None
        except Exception as caught:
            result = None
            error = str(caught)
        self._worker_results.put(
            _WorkerEvent("analysis", request_id, (request, result, error))
        )

    def _finish_analysis(
        self,
        request_id: int,
        request: AnalysisRequest,
        result: CompileResult | None,
        error: str | None,
    ) -> None:
        if request_id != self._generation:
            return
        self._set_running(False)
        if error is not None or result is None:
            self.status_var.set(t("status.analysis_failed"))
            messagebox.showerror(
                APP_NAME, t("msg.llm_failed", err=error or "Unknown error")
            )
            return
        self._last_result = result
        self._last_source = request.source_text
        self._result_stale = self.text.get("1.0", "end-1c") != request.source_text
        self._populate_diagnostics(result)
        self._render_last_result()
        if self._result_stale:
            self.status_var.set(t("status.results_stale"))
        elif result.clean:
            self.status_var.set(t("run.no_output"))
        else:
            self.status_var.set(t("status.issue_count", count=len(result.diagnostics)))

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.run_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.style_box.configure(state="disabled" if running else "readonly")

    def cancel_analysis(self) -> None:
        if not self._running:
            return
        self._generation += 1
        self._set_running(False)
        self.status_var.set(t("status.cancelled"))

    def _populate_diagnostics(self, result: CompileResult) -> None:
        for item in self.issues.get_children():
            self.issues.delete(item)
        self._clear_highlights()
        for index, diagnostic in enumerate(result.diagnostics):
            self.issues.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    diagnostic.line,
                    diagnostic.severity,
                    diagnostic.message,
                ),
            )
            if not self._result_stale:
                self._highlight_diagnostic(diagnostic)

    def _highlight_diagnostic(self, diagnostic: Diagnostic) -> None:
        start = f"{diagnostic.line}.{diagnostic.start_column - 1}"
        end_column = max(diagnostic.end_column - 1, diagnostic.start_column)
        end = f"{diagnostic.line}.{end_column}"
        self.text.tag_add(f"diagnostic_{diagnostic.severity}", start, end)

    def _clear_highlights(self) -> None:
        for severity in ("error", "warning", "info", "hint"):
            self.text.tag_remove(f"diagnostic_{severity}", "1.0", "end")

    def _render_last_result(self) -> None:
        if self._last_result is None:
            return
        output = render_diagnostics(
            self.default_style_var.get(),
            self._last_result,
            self._last_source,
        )
        self._set_output(output or t("run.no_output"))

    def _set_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def jump_to_selected_diagnostic(self, _event=None):
        selected = self.issues.selection()
        if not selected or self._last_result is None:
            return "break"
        if self._result_stale:
            self.status_var.set(t("status.results_stale"))
            return "break"
        diagnostic = self._last_result.diagnostics[int(selected[0])]
        index = f"{diagnostic.line}.{diagnostic.start_column - 1}"
        self.text.mark_set("insert", index)
        self.text.see(index)
        self.text.focus_set()
        self.update_cursor_status()
        return "break"

    def copy_output(self) -> None:
        content = self.output.get("1.0", "end-1c")
        if not content:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            self.status_var.set(t("warn.copy_ok"))
        except tk.TclError as error:
            messagebox.showerror(APP_NAME, t("warn.copy_failed", err=str(error)))

    def save_log(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[
                (t("filetype.log"), "*.log"),
                (t("filetype.text"), "*.txt"),
                (t("filetype.all"), "*.*"),
            ],
        )
        if not path:
            return
        try:
            write_text_utf8(path, self.output.get("1.0", "end-1c"))
        except (OSError, UnicodeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("warn.save_log_failed", err=str(error)))

    def on_close(self) -> None:
        if not self.confirm_discard():
            return
        self._closing = True
        self._generation += 1
        self._test_generation += 1
        if self._worker_poll_id is not None:
            try:
                self.after_cancel(self._worker_poll_id)
            except tk.TclError:
                pass
            self._worker_poll_id = None
        try:
            unregister_listener(self.on_lang_changed)
        except ValueError:
            pass
        self.destroy()


class LLMSettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg: ConfigManager, llm: LLMClient):
        super().__init__(master)
        self.cfg = cfg
        self.llm = llm
        self.title(t("llm.title"))
        self.minsize(560, 500)
        self.geometry(_fitted_geometry(self, 720, 620, 560, 500))
        self.resizable(True, True)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._closed = False
        self._test_generation = 0
        self._worker_results: queue.Queue[_WorkerEvent] = queue.Queue()
        self._worker_poll_id: str | None = None
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, **pad)
        frm.columnconfigure(1, weight=1)

        self.base_url = tk.StringVar(value=cfg.get_nested("llm", "base_url") or "")
        self.model = tk.StringVar(value=cfg.get_nested("llm", "model") or "")
        stored_key = cfg.get_nested("llm", "api_key") or ""
        self.api_key = tk.StringVar(value=stored_key)
        self.key_source = tk.StringVar(value="local" if stored_key else "environment")
        self.header_name = tk.StringVar(
            value=cfg.get_nested("llm", "auth", "header_name") or ""
        )
        self.header_prefix = tk.StringVar(
            value=cfg.get_nested("llm", "auth", "prefix") or ""
        )
        self.temperature = tk.DoubleVar(
            value=self._safe_float(cfg.get_nested("llm", "temperature"), 0.1)
        )
        self.max_tokens = tk.IntVar(
            value=self._safe_int(cfg.get_nested("llm", "max_tokens"), 900)
        )
        self.token_parameter = tk.StringVar(
            value=cfg.get_nested("llm", "token_parameter") or "max_tokens"
        )
        self.timeout = tk.IntVar(
            value=self._safe_int(cfg.get_nested("llm", "timeout_seconds"), 60)
        )

        row = 0
        self.lbl_base = ttk.Label(frm, text=t("llm.base_url"))
        self.lbl_base.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.base_url, width=50).grid(
            row=row, column=1, sticky="ew", **pad
        )
        row += 1
        self.lbl_model = ttk.Label(frm, text=t("llm.model"))
        self.lbl_model.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.model, width=30).grid(
            row=row, column=1, sticky="ew", **pad
        )
        row += 1
        self.lbl_key = ttk.Label(frm, text=t("llm.api_key"))
        self.lbl_key.grid(row=row, column=0, sticky="e", **pad)
        self.key_entry = ttk.Entry(frm, textvariable=self.api_key, width=50, show="*")
        self.key_entry.grid(row=row, column=1, sticky="ew", **pad)
        row += 1
        self.key_source_frame = ttk.Frame(frm)
        self.key_source_frame.grid(row=row, column=1, sticky="w", **pad)
        self.key_environment = ttk.Radiobutton(
            self.key_source_frame,
            variable=self.key_source,
            value="environment",
            command=self._update_key_source,
        )
        self.key_environment.pack(anchor="w")
        self.key_local = ttk.Radiobutton(
            self.key_source_frame,
            variable=self.key_source,
            value="local",
            command=self._update_key_source,
        )
        self.key_local.pack(anchor="w")
        row += 1
        self.lbl_hname = ttk.Label(frm, text=t("llm.header_name"))
        self.lbl_hname.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.header_name, width=30).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1
        self.lbl_hprefix = ttk.Label(frm, text=t("llm.header_prefix"))
        self.lbl_hprefix.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.header_prefix, width=30).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1
        self.lbl_temp = ttk.Label(frm, text=t("llm.temperature"))
        self.lbl_temp.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.temperature, width=10).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1
        self.lbl_max = ttk.Label(frm, text=t("llm.max_tokens"))
        self.lbl_max.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.max_tokens, width=10).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1
        self.lbl_token_parameter = ttk.Label(frm, text=t("llm.token_parameter"))
        self.lbl_token_parameter.grid(row=row, column=0, sticky="e", **pad)
        self.token_parameter_box = ttk.Combobox(
            frm,
            textvariable=self.token_parameter,
            values=("max_tokens", "max_completion_tokens"),
            state="readonly",
            width=24,
        )
        self.token_parameter_box.grid(row=row, column=1, sticky="w", **pad)
        row += 1
        self.lbl_timeout = ttk.Label(frm, text=t("llm.timeout"))
        self.lbl_timeout.grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.timeout, width=10).grid(
            row=row, column=1, sticky="w", **pad
        )
        row += 1

        self.security_note = ttk.Label(
            frm, text=t("llm.security_note"), foreground="red", wraplength=560
        )
        self.security_note.grid(row=row, column=0, columnspan=2, sticky="w", **pad)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", **pad)
        self.btn_save = ttk.Button(btns, text=t("styles.save"), command=self.on_save)
        self.btn_save.pack(side="right", padx=4)
        self.btn_test = ttk.Button(
            btns, text=t("settings.test_llm"), command=self.on_test
        )
        self.btn_test.pack(side="right", padx=4)
        self.btn_close = ttk.Button(btns, text=t("styles.close"), command=self.destroy)
        self.btn_close.pack(side="right", padx=4)

        register_listener(self.on_lang_changed)
        self.on_lang_changed(get_language())
        self._update_key_source()
        self._schedule_worker_poll()

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

    def _update_key_source(self) -> None:
        state = "normal" if self.key_source.get() == "local" else "disabled"
        self.key_entry.configure(state=state)

    def _build_llm_overrides(self):
        try:
            temperature = float(self.temperature.get())
            max_tokens = int(self.max_tokens.get())
            timeout = int(self.timeout.get())
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(e)))
            return None
        overrides = {
            "llm": {
                "base_url": self.base_url.get().strip(),
                "model": self.model.get().strip(),
                "api_key": (
                    self.api_key.get().strip()
                    if self.key_source.get() == "local"
                    else ""
                ),
                "auth": {
                    "header_name": self.header_name.get().strip(),
                    "prefix": self.header_prefix.get(),
                },
                "temperature": temperature,
                "max_tokens": max_tokens,
                "token_parameter": self.token_parameter.get(),
                "timeout_seconds": timeout,
            }
        }
        try:
            self.llm.validate_overrides(overrides)
        except (TypeError, ValueError) as error:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))
            return None
        return overrides

    def on_lang_changed(self, lang: str):
        self.title(t("llm.title"))
        self.lbl_base.configure(text=t("llm.base_url"))
        self.lbl_model.configure(text=t("llm.model"))
        self.lbl_key.configure(text=t("llm.api_key"))
        self.lbl_hname.configure(text=t("llm.header_name"))
        self.lbl_hprefix.configure(text=t("llm.header_prefix"))
        self.lbl_temp.configure(text=t("llm.temperature"))
        self.lbl_max.configure(text=t("llm.max_tokens"))
        self.lbl_token_parameter.configure(text=t("llm.token_parameter"))
        self.lbl_timeout.configure(text=t("llm.timeout"))
        self.key_environment.configure(text=t("llm.key_source.environment"))
        self.key_local.configure(text=t("llm.key_source.local"))
        self.security_note.configure(text=t("llm.security_note"))
        self.btn_save.configure(text=t("styles.save"))
        self.btn_test.configure(text=t("settings.test_llm"))
        self.btn_close.configure(text=t("styles.close"))

    def on_save(self):
        try:
            overrides = self._build_llm_overrides()
            if overrides is None:
                return
            self.cfg.update({"llm": overrides["llm"]})
            messagebox.showinfo(APP_NAME, t("msg.config_saved"))
        except Exception as e:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(e)))

    def on_test(self):
        if getattr(self, "_testing", False):
            return
        overrides = self._build_llm_overrides()
        if overrides is None:
            return
        try:
            snapshot = self.llm.prepare_connectivity(overrides=overrides)
        except Exception as error:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=str(error)))
            return
        self._testing = True
        self._test_generation += 1
        request_id = self._test_generation
        self.btn_test.configure(state="disabled")
        threading.Thread(
            target=self._do_test,
            args=(request_id, snapshot),
            daemon=True,
        ).start()

    def _do_test(self, request_id: int, snapshot: RequestSnapshot):
        try:
            ok, msg = self.llm.run_connectivity(snapshot)
        except Exception as e:
            ok, msg = False, str(e)
        self._worker_results.put(_WorkerEvent("connectivity", request_id, (ok, msg)))

    def _schedule_worker_poll(self) -> None:
        if self._closed or self._worker_poll_id is not None:
            return
        self._worker_poll_id = self.after(WORKER_POLL_MS, self._poll_worker_results)

    def _poll_worker_results(self) -> None:
        self._worker_poll_id = None
        if self._closed:
            return
        while True:
            try:
                event = self._worker_results.get_nowait()
            except queue.Empty:
                break
            if (
                event.kind == "connectivity"
                and event.generation == self._test_generation
            ):
                ok, msg = event.payload
                self._finish_test(bool(ok), str(msg))
        self._schedule_worker_poll()

    def _finish_test(self, ok: bool, msg: str):
        self._testing = False
        self.btn_test.configure(state="normal")
        if ok:
            messagebox.showinfo(APP_NAME, t("msg.llm_test_ok"))
        else:
            messagebox.showerror(APP_NAME, t("msg.llm_test_fail", err=msg))

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        self._test_generation += 1
        if self._worker_poll_id is not None:
            try:
                self.after_cancel(self._worker_poll_id)
            except tk.TclError:
                pass
            self._worker_poll_id = None
        try:
            unregister_listener(self.on_lang_changed)
        except Exception:
            pass
        super().destroy()


class StylesDialog(tk.Toplevel):
    def __init__(
        self, master, styles: StyleManager, cfg: ConfigManager, on_changed=None
    ):
        super().__init__(master)
        self.styles = styles
        self.cfg = cfg
        self._on_changed = on_changed
        self.title(t("styles.title"))
        self.minsize(760, 460)
        self.geometry(_fitted_geometry(self, 900, 540, 760, 460))
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=8, pady=8)
        left = ttk.Frame(container)
        right = ttk.Frame(container)
        left.pack(side="left", fill="y")
        right.pack(side="right", fill="both", expand=True)

        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", padx=4, pady=4)
        self.listbox = tk.Listbox(list_frame, height=20)
        list_scroll = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.listbox.yview
        )
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.pack(side="left", fill="y")
        list_scroll.pack(side="right", fill="y")
        for n in self.styles.names:
            self.listbox.insert("end", n)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        btns = ttk.Frame(left)
        btns.pack(side="top", pady=6)
        self.add_btn = ttk.Button(btns, text=t("styles.add"), command=self.on_add)
        self.add_btn.grid(row=0, column=0, padx=4)
        self.edit_btn = ttk.Button(btns, text=t("styles.edit"), command=self.on_edit)
        self.edit_btn.grid(row=0, column=1, padx=4)
        self.delete_btn = ttk.Button(
            btns, text=t("styles.delete"), command=self.on_delete
        )
        self.delete_btn.grid(row=0, column=2, padx=4)
        self.close_btn = ttk.Button(btns, text=t("styles.close"), command=self.destroy)
        self.close_btn.grid(row=0, column=3, padx=4)

        self.name_var = tk.StringVar()
        template_frame = ttk.Frame(right)
        self.template = tk.Text(template_frame, wrap="word", width=50, height=18)
        template_scroll = ttk.Scrollbar(
            template_frame, orient="vertical", command=self.template.yview
        )
        self.template.configure(yscrollcommand=template_scroll.set)
        self.hint = ttk.Label(
            right,
            text=t("styles.example_hint"),
            wraplength=430,
            justify="left",
        )
        self.lbl_name = ttk.Label(right, text=t("styles.name"))
        self.lbl_name.pack(anchor="w")
        ttk.Entry(right, textvariable=self.name_var, width=40).pack(
            fill="x", padx=2, pady=2
        )
        self.lbl_template = ttk.Label(right, text=t("styles.template"))
        self.lbl_template.pack(anchor="w")
        template_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.template.pack(side="left", fill="both", expand=True)
        template_scroll.pack(side="right", fill="y")

        self.save_btn = ttk.Button(right, text=t("styles.save"), command=self.on_save)
        self.save_btn.pack(anchor="e", pady=4)
        self.hint.pack(anchor="w", fill="x")

        register_listener(self.on_lang_changed)

    def on_lang_changed(self, lang: str):
        self.title(t("styles.title"))
        self.hint.configure(text=t("styles.example_hint"))
        self.lbl_name.configure(text=t("styles.name"))
        self.lbl_template.configure(text=t("styles.template"))
        self.save_btn.configure(text=t("styles.save"))
        self.add_btn.configure(text=t("styles.add"))
        self.edit_btn.configure(text=t("styles.edit"))
        self.delete_btn.configure(text=t("styles.delete"))
        self.close_btn.configure(text=t("styles.close"))

    def on_select(self, evt=None):
        sel = self._selected_name()
        if not sel:
            return
        self.name_var.set(sel)
        self.template.delete("1.0", "end")
        self.template.insert("1.0", self.styles.get(sel))

    def on_add(self):
        self.name_var.set("NewStyle")
        self.template.delete("1.0", "end")
        self.template.insert(
            "1.0",
            "Review terminology, punctuation, and clarity using the "
            "{style_name} profile.",
        )

    def on_edit(self):
        name = self._selected_name()
        if not name:
            messagebox.showwarning(APP_NAME, t("warn.no_style"))
            return
        self.name_var.set(name)
        self.template.delete("1.0", "end")
        self.template.insert("1.0", self.styles.get(name))
        self.template.focus_set()

    def on_delete(self):
        name = self._selected_name()
        if not name:
            return
        try:
            if name in BUILTIN_STYLES:
                data = self.cfg.get("styles", {}) or {}
                if not isinstance(data, dict):
                    data = {}
                if name in data:
                    del data[name]
                    self.cfg.set("styles", data)
            else:
                self.styles.delete(name)
        except Exception as error:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))
            return
        self.refresh_list()
        self._notify_styles_changed()

    def on_save(self):
        name = (self.name_var.get() or "").strip()
        if not name:
            messagebox.showwarning(APP_NAME, t("warn.no_style"))
            return
        template = self.template.get("1.0", "end-1c")
        try:
            self.styles.set(name, template)
        except Exception as error:
            messagebox.showerror(APP_NAME, t("msg.config_failed", err=str(error)))
            return
        self.refresh_list()
        self._notify_styles_changed()

    def refresh_list(self):
        self.styles.reload()
        self.listbox.delete(0, "end")
        for n in self.styles.names:
            self.listbox.insert("end", n)

    def _notify_styles_changed(self):
        if self._on_changed:
            try:
                self._on_changed()
            except Exception:
                pass

    def _selected_name(self) -> Optional[str]:
        sel = self.listbox.curselection()
        if not sel:
            return None
        return self.listbox.get(sel[0])

    def destroy(self):
        try:
            unregister_listener(self.on_lang_changed)
        except Exception:
            pass
        super().destroy()


def main():
    app = TypoCompilerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
