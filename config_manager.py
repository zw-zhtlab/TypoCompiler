# config_manager.py
import json, os
from copy import deepcopy
from typing import Any, Dict

APP_DIR = os.path.join(os.path.expanduser("~"), ".typocompiler")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "language": "zh",
    "font_size": 12,
    "default_style": "Python",
    "recent_files": [],
    "llm": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key": "",
        "auth": {"header_name": "Authorization", "prefix": "Bearer "},
        "temperature": 0.1,
        "max_tokens": 900,
        "timeout_seconds": 60
    },
    "styles": {}
}

class ConfigManager:
    def __init__(self, path: str = CONFIG_PATH) -> None:
        self.path = path
        self._config = None
        self._reset_notice = False
        self.ensure_loaded()

    def ensure_loaded(self) -> None:
        self._ensure_parent_dir()
        if not os.path.exists(self.path):
            self._config = deepcopy(DEFAULT_CONFIG)
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except Exception:
            self._reset_to_defaults(backup_broken=True)
            return
        if not isinstance(self._config, dict):
            self._reset_to_defaults(backup_broken=True)
            return
        changed = self._deep_merge_missing(self._config, DEFAULT_CONFIG)
        if self._normalize_schema():
            changed = True
        if changed:
            self.save()

    def _deep_merge_missing(self, target: Dict[str, Any], default: Dict[str, Any]) -> bool:
        changed = False
        for k, v in default.items():
            if k not in target:
                target[k] = deepcopy(v)
                changed = True
            elif isinstance(v, dict) and isinstance(target[k], dict):
                if self._deep_merge_missing(target[k], v):
                    changed = True
        return changed

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(os.path.abspath(self.path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    def _reset_to_defaults(self, backup_broken: bool) -> None:
        self._reset_notice = True
        if backup_broken:
            try:
                backup = self.path + ".broken"
                if os.path.exists(self.path):
                    os.replace(self.path, backup)
            except Exception:
                pass
        self._config = deepcopy(DEFAULT_CONFIG)
        self.save()

    @staticmethod
    def _as_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_schema(self) -> bool:
        changed = False
        cfg = self._config

        language = cfg.get("language")
        if not isinstance(language, str) or not language:
            cfg["language"] = DEFAULT_CONFIG["language"]
            changed = True

        default_style = cfg.get("default_style")
        if not isinstance(default_style, str) or not default_style:
            cfg["default_style"] = DEFAULT_CONFIG["default_style"]
            changed = True

        font_size_raw = cfg.get("font_size")
        font_size = self._as_int(font_size_raw, DEFAULT_CONFIG["font_size"])
        if font_size != font_size_raw:
            cfg["font_size"] = font_size
            changed = True

        recent = cfg.get("recent_files")
        if not isinstance(recent, list):
            cfg["recent_files"] = []
            changed = True
        else:
            normalized_recent = []
            for p in recent:
                if isinstance(p, str) and p:
                    normalized_recent.append(p)
            normalized_recent = normalized_recent[:10]
            if normalized_recent != recent:
                cfg["recent_files"] = normalized_recent
                changed = True

        styles = cfg.get("styles")
        if not isinstance(styles, dict):
            cfg["styles"] = {}
            changed = True
        else:
            normalized_styles = {}
            for k, v in styles.items():
                if isinstance(k, str) and isinstance(v, str):
                    normalized_styles[k] = v
                else:
                    changed = True
            if normalized_styles != styles:
                cfg["styles"] = normalized_styles
                changed = True

        llm = cfg.get("llm")
        if not isinstance(llm, dict):
            cfg["llm"] = deepcopy(DEFAULT_CONFIG["llm"])
            return True

        for key in ("base_url", "model", "api_key"):
            value = llm.get(key)
            if not isinstance(value, str):
                llm[key] = DEFAULT_CONFIG["llm"][key]
                changed = True

        auth = llm.get("auth")
        if not isinstance(auth, dict):
            llm["auth"] = deepcopy(DEFAULT_CONFIG["llm"]["auth"])
            auth = llm["auth"]
            changed = True
        for key in ("header_name", "prefix"):
            value = auth.get(key)
            if not isinstance(value, str):
                auth[key] = DEFAULT_CONFIG["llm"]["auth"][key]
                changed = True

        temp_raw = llm.get("temperature")
        temp = self._as_float(temp_raw, DEFAULT_CONFIG["llm"]["temperature"])
        if temp != temp_raw:
            llm["temperature"] = temp
            changed = True

        max_tokens_raw = llm.get("max_tokens")
        max_tokens = self._as_int(max_tokens_raw, DEFAULT_CONFIG["llm"]["max_tokens"])
        if max_tokens != max_tokens_raw:
            llm["max_tokens"] = max_tokens
            changed = True

        timeout_raw = llm.get("timeout_seconds")
        timeout = self._as_int(timeout_raw, DEFAULT_CONFIG["llm"]["timeout_seconds"])
        if timeout != timeout_raw:
            llm["timeout_seconds"] = timeout
            changed = True

        return changed

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        self._config[key] = value
        self.save()

    def get_nested(self, *keys, default=None):
        node = self._config
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set_nested(self, *keys_and_value) -> None:
        *keys, value = keys_and_value
        node = self._config
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value
        self.save()

    def add_recent_file(self, path: str) -> None:
        lst = self._config.get("recent_files", [])
        if not isinstance(lst, list):
            lst = []
        path = str(path)
        while path in lst:
            lst.remove(path)
        lst.insert(0, path)
        self._config["recent_files"] = lst[:10]
        self.save()

    def consume_reset_notice(self) -> bool:
        if self._reset_notice:
            self._reset_notice = False
            return True
        return False

    def save(self) -> None:
        self._ensure_parent_dir()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
