# i18n.py
from typing import Callable, Dict, List

DICT: Dict[str, Dict[str, str]] = {
    "en": {
        "app.title": "TypoCompiler",
        "menu.file": "File",
        "menu.settings": "Settings",
        "menu.run": "Run",
        "file.new": "New",
        "file.open": "Open...",
        "file.save": "Save",
        "file.save_as": "Save As...",
        "file.recent": "Recent Files",
        "file.exit": "Exit",
        "recent.empty": "(empty)",
        "settings.language": "Language",
        "settings.lang.zh": "Chinese",
        "settings.lang.en": "English",
        "settings.default_style": "Default Error Style",
        "settings.manage_styles": "Manage Styles...",
        "settings.llm": "LLM Settings...",
        "settings.test_llm": "Test LLM",
        "settings.font": "Font Size",
        "settings.font.inc": "Increase",
        "settings.font.dec": "Decrease",
        "settings.font.reset": "Reset",
        "run.run": "Run",
        "run.choose_style": "Choose Style",
        "run.open": "Run",
        "run.window.title": "Compiler Output",
        "run.copy": "Copy",
        "run.save_log": "Save Log...",
        "run.close": "Close",
        "run.running": "Running...",
        "run.ready": "Ready",
        "run.no_output": "No compiler output (no issues detected).",
        "dialog.ok": "OK",
        "dialog.cancel": "Cancel",
        "dialog.yes": "Yes",
        "dialog.no": "No",
        "status.ready": "Ready",
        "status.loaded": "Loaded: {name}",
        "status.saved": "Saved: {name}",
        "status.testing_llm": "Testing LLM connectivity...",
        "msg.confirm_overwrite": "File exists. Overwrite?",
        "msg.save_failed": "Save failed: {err}",
        "msg.open_failed": "Open failed: {err}",
        "msg.config_saved": "Settings saved.",
        "msg.config_failed": "Failed to save settings: {err}",
        "msg.llm_test_ok": "LLM connectivity OK.",
        "msg.llm_test_fail": "LLM connectivity failed:\n{err}",
        "msg.llm_failed": "LLM request failed:\n{err}",
        "llm.title": "LLM Settings",
        "llm.base_url": "Base URL (OpenAI-compatible)",
        "llm.model": "Model",
        "llm.api_key": "API Key / Token",
        "llm.header_name": "Auth Header Name",
        "llm.header_prefix": "Auth Header Prefix",
        "llm.temperature": "Temperature",
        "llm.max_tokens": "Max Tokens",
        "llm.timeout": "Timeout (seconds)",
        "llm.security_note": "Note: API keys are stored locally in plain text. Prefer using a scoped token.",
        "styles.title": "Manage Styles",
        "styles.name": "Name",
        "styles.template": "Template",
        "styles.add": "Add",
        "styles.edit": "Edit",
        "styles.delete": "Delete",
        "styles.save": "Save",
        "styles.close": "Close",
        "styles.example_hint": "Template placeholders: {input_text}, {style_name}",
        "warn.no_text": "Please enter English natural-language text to 'compile'.",
        "warn.no_style": "No style selected.",
        "warn.unsaved": "You have unsaved changes. Discard them?",
        "warn.save_log_failed": "Failed to save log: {err}",
        "warn.copy_ok": "Copied to clipboard.",
        "warn.copy_failed": "Copy failed: {err}",
        "info.reset_defaults": "Configuration file was missing or corrupted and has been reset to defaults.",
    },
    "zh": {
        "app.title": "TypoCompiler",
        "menu.file": "文件",
        "menu.settings": "设置",
        "menu.run": "运行",
        "file.new": "新建",
        "file.open": "打开...",
        "file.save": "保存",
        "file.save_as": "另存为...",
        "file.recent": "最近打开",
        "file.exit": "退出",
        "recent.empty": "（空）",
        "settings.language": "界面语言",
        "settings.lang.zh": "中文",
        "settings.lang.en": "英文",
        "settings.default_style": "默认报错风格",
        "settings.manage_styles": "管理风格...",
        "settings.llm": "LLM 设置...",
        "settings.test_llm": "测试连通性",
        "settings.font": "字号",
        "settings.font.inc": "增大",
        "settings.font.dec": "减小",
        "settings.font.reset": "重置",
        "run.run": "运行",
        "run.choose_style": "选择风格",
        "run.open": "运行",
        "run.window.title": "编译输出",
        "run.copy": "复制",
        "run.save_log": "保存日志...",
        "run.close": "关闭",
        "run.running": "运行中...",
        "run.ready": "就绪",
        "run.no_output": "无编译器输出（未发现问题）。",
        "dialog.ok": "确定",
        "dialog.cancel": "取消",
        "dialog.yes": "是",
        "dialog.no": "否",
        "status.ready": "就绪",
        "status.loaded": "已打开：{name}",
        "status.saved": "已保存：{name}",
        "status.testing_llm": "正在测试 LLM 连通性...",
        "msg.confirm_overwrite": "文件已存在，是否覆盖？",
        "msg.save_failed": "保存失败：{err}",
        "msg.open_failed": "打开失败：{err}",
        "msg.config_saved": "设置已保存。",
        "msg.config_failed": "保存设置失败：{err}",
        "msg.llm_test_ok": "LLM 连通性正常。",
        "msg.llm_test_fail": "LLM 连通性失败：\n{err}",
        "msg.llm_failed": "LLM 请求失败：\n{err}",
        "llm.title": "LLM 设置",
        "llm.base_url": "基础地址（OpenAI 协议）",
        "llm.model": "模型",
        "llm.api_key": "API Key / Token",
        "llm.header_name": "鉴权头名称",
        "llm.header_prefix": "鉴权头前缀",
        "llm.temperature": "温度",
        "llm.max_tokens": "最大 Token",
        "llm.timeout": "超时（秒）",
        "llm.security_note": "提示：API Key 将以明文保存在本地，请尽量使用权限受限的 Token。",
        "styles.title": "风格管理",
        "styles.name": "名称",
        "styles.template": "模板",
        "styles.add": "新增",
        "styles.edit": "编辑",
        "styles.delete": "删除",
        "styles.save": "保存",
        "styles.close": "关闭",
        "styles.example_hint": "模板可用占位符：{input_text}、{style_name}",
        "warn.no_text": "请输入要“编译”的英文自然语言文本。",
        "warn.no_style": "请选择风格。",
        "warn.unsaved": "当前内容尚未保存，确定要放弃更改吗？",
        "warn.save_log_failed": "保存日志失败：{err}",
        "warn.copy_ok": "已复制到剪贴板。",
        "warn.copy_failed": "复制失败：{err}",
        "info.reset_defaults": "配置文件缺失或损坏，已恢复为默认设置。",
    },
}

_current_lang: str = "zh"
_listeners: List[Callable[[str], None]] = []


def set_language(lang: str) -> None:
    global _current_lang
    if lang not in DICT:
        lang = "en"
    _current_lang = lang
    for cb in list(_listeners):
        try:
            cb(lang)
        except Exception:
            pass


def get_language() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    d = DICT.get(_current_lang, {})
    text = d.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def register_listener(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def unregister_listener(callback: Callable[[str], None]) -> None:
    if callback in _listeners:
        _listeners.remove(callback)
