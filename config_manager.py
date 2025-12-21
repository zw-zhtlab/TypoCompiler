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
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._config = deepcopy(DEFAULT_CONFIG)
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except Exception:
            self._reset_notice = True
            try:
                backup = self.path + ".broken"
                if os.path.exists(self.path):
                    os.replace(self.path, backup)
            except Exception:
                pass
            self._config = deepcopy(DEFAULT_CONFIG)
            self.save()
        if self._deep_merge_missing(self._config, DEFAULT_CONFIG):
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
        if path in lst:
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
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)
