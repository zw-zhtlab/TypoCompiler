"""Thread-safe, validated, and crash-safe application configuration."""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict

APP_DIR = os.path.join(os.path.expanduser("~"), ".typocompiler")
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
MAX_CONFIG_BYTES = 1024 * 1024

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
        "token_parameter": "max_tokens",
        "timeout_seconds": 60,
    },
    "styles": {},
}


def _freeze(value: Any) -> Any:
    """Return a recursively immutable view over a detached configuration copy."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _fsync_directory(path: str) -> None:
    """Best-effort directory sync; unsupported on some platforms, notably Windows."""
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


class ConfigManager:
    """Own application configuration and persist each change as one transaction."""

    def __init__(self, path: str | None = None) -> None:
        if path is None:
            path = os.environ.get("TYPOCOMPILER_CONFIG_PATH") or CONFIG_PATH
        self.path = os.path.abspath(os.fspath(path))
        self._lock = threading.RLock()
        self._config: Dict[str, Any] = {}
        self._reset_notice = False
        self.ensure_loaded()

    def ensure_loaded(self) -> None:
        with self._lock:
            self._ensure_parent_dir()
            if not os.path.exists(self.path):
                self._config = deepcopy(DEFAULT_CONFIG)
                self._save_locked()
                return
            try:
                loaded = self._read_config_file()
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                self._reset_to_defaults(backup_broken=True)
                return
            if not isinstance(loaded, dict):
                self._reset_to_defaults(backup_broken=True)
                return
            self._config = loaded
            changed = self._deep_merge_missing(self._config, DEFAULT_CONFIG)
            changed = self._normalize_schema() or changed
            if changed:
                self._save_locked()

    def _read_config_file(self) -> Any:
        try:
            size = os.path.getsize(self.path)
        except OSError:
            size = None
        if size is not None and size > MAX_CONFIG_BYTES:
            raise ValueError(
                f"Configuration exceeds the {MAX_CONFIG_BYTES}-byte safety limit"
            )
        with open(self.path, "rb") as config_file:
            raw = config_file.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError(
                f"Configuration exceeds the {MAX_CONFIG_BYTES}-byte safety limit"
            )
        return json.loads(raw.decode("utf-8"))

    def _deep_merge_missing(
        self, target: Dict[str, Any], default: Dict[str, Any]
    ) -> bool:
        changed = False
        for key, value in default.items():
            if key not in target:
                target[key] = deepcopy(value)
                changed = True
            elif isinstance(value, dict) and isinstance(target[key], dict):
                changed = self._deep_merge_missing(target[key], value) or changed
        return changed

    def _ensure_parent_dir(self) -> None:
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
            if os.path.normcase(os.path.abspath(parent)) == os.path.normcase(
                os.path.abspath(APP_DIR)
            ):
                try:
                    os.chmod(parent, 0o700)
                except OSError:
                    pass

    def _reset_to_defaults(self, backup_broken: bool) -> None:
        self._reset_notice = True
        backup_failed = False
        if backup_broken and os.path.exists(self.path):
            backup_failed = self._backup_broken_config() is None and os.path.exists(
                self.path
            )
        self._config = deepcopy(DEFAULT_CONFIG)
        if backup_failed:
            # Preserve the corrupt evidence if it could not be moved safely. The
            # application can still run with in-memory defaults for this session.
            return
        self._save_locked()

    def _backup_broken_config(self) -> str | None:
        """Move a broken config aside without replacing earlier forensic evidence."""

        for _attempt in range(10):
            candidate = f"{self.path}.broken-{uuid.uuid4().hex}"
            if os.path.exists(candidate):
                continue
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
            try:
                os.rename(self.path, candidate)
            except FileExistsError:
                continue
            except OSError:
                # Recovery must still leave the app usable if backup creation fails.
                return None
            try:
                os.chmod(candidate, 0o600)
            except OSError:
                pass
            return candidate
        return None

    @staticmethod
    def _as_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, float) and not value.is_integer():
            return default
        try:
            converted = int(value)
        except (TypeError, ValueError, OverflowError):
            return default
        if not minimum <= converted <= maximum:
            return default
        return converted

    @staticmethod
    def _as_float(value: Any, default: float, minimum: float, maximum: float) -> float:
        if isinstance(value, bool):
            return default
        try:
            converted = float(value)
        except (TypeError, ValueError, OverflowError):
            return default
        if not math.isfinite(converted) or not minimum <= converted <= maximum:
            return default
        return converted

    def _normalize_schema(self) -> bool:
        changed = False
        config = self._config

        language = config.get("language")
        if not isinstance(language, str) or not language:
            config["language"] = DEFAULT_CONFIG["language"]
            changed = True

        default_style = config.get("default_style")
        if not isinstance(default_style, str) or not default_style:
            config["default_style"] = DEFAULT_CONFIG["default_style"]
            changed = True

        font_size_raw = config.get("font_size")
        font_size = self._as_int(
            font_size_raw, DEFAULT_CONFIG["font_size"], minimum=8, maximum=40
        )
        if type(font_size_raw) is not int or font_size != font_size_raw:
            config["font_size"] = font_size
            changed = True

        recent = config.get("recent_files")
        if not isinstance(recent, list):
            config["recent_files"] = []
            changed = True
        else:
            normalized_recent = [
                path for path in recent if isinstance(path, str) and path
            ][:10]
            if normalized_recent != recent:
                config["recent_files"] = normalized_recent
                changed = True

        styles = config.get("styles")
        if not isinstance(styles, dict):
            config["styles"] = {}
            changed = True
        else:
            normalized_styles = {
                key: value
                for key, value in styles.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            if normalized_styles != styles:
                config["styles"] = normalized_styles
                changed = True

        llm = config.get("llm")
        if not isinstance(llm, dict):
            config["llm"] = deepcopy(DEFAULT_CONFIG["llm"])
            return True

        for key in ("base_url", "model", "api_key"):
            if not isinstance(llm.get(key), str):
                llm[key] = DEFAULT_CONFIG["llm"][key]
                changed = True

        auth = llm.get("auth")
        if not isinstance(auth, dict):
            llm["auth"] = deepcopy(DEFAULT_CONFIG["llm"]["auth"])
            auth = llm["auth"]
            changed = True
        for key in ("header_name", "prefix"):
            if not isinstance(auth.get(key), str):
                auth[key] = DEFAULT_CONFIG["llm"]["auth"][key]
                changed = True

        temperature_raw = llm.get("temperature")
        temperature = self._as_float(
            temperature_raw,
            DEFAULT_CONFIG["llm"]["temperature"],
            minimum=0.0,
            maximum=2.0,
        )
        if (
            isinstance(temperature_raw, bool)
            or not isinstance(temperature_raw, (int, float))
            or temperature != temperature_raw
        ):
            llm["temperature"] = temperature
            changed = True

        max_tokens_raw = llm.get("max_tokens")
        max_tokens = self._as_int(
            max_tokens_raw,
            DEFAULT_CONFIG["llm"]["max_tokens"],
            minimum=1,
            maximum=1_000_000,
        )
        if type(max_tokens_raw) is not int or max_tokens != max_tokens_raw:
            llm["max_tokens"] = max_tokens
            changed = True

        token_parameter = llm.get("token_parameter")
        if token_parameter not in {"max_tokens", "max_completion_tokens"}:
            llm["token_parameter"] = DEFAULT_CONFIG["llm"]["token_parameter"]
            changed = True

        timeout_raw = llm.get("timeout_seconds")
        timeout = self._as_int(
            timeout_raw,
            DEFAULT_CONFIG["llm"]["timeout_seconds"],
            minimum=1,
            maximum=3_600,
        )
        if type(timeout_raw) is not int or timeout != timeout_raw:
            llm["timeout_seconds"] = timeout
            changed = True

        return changed

    def snapshot(self) -> Mapping[str, Any]:
        """Return a detached, recursively immutable request-safe snapshot."""
        with self._lock:
            return _freeze(deepcopy(self._config))

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return deepcopy(self._config.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self.update({key: value})

    def update(self, values: Mapping[str, Any]) -> None:
        """Atomically validate and persist multiple top-level values."""
        detached = deepcopy(dict(values))

        def mutate() -> None:
            self._config.update(detached)

        self._commit(mutate)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._config
            for key in keys:
                if not isinstance(node, dict) or key not in node:
                    return deepcopy(default)
                node = node[key]
            return deepcopy(node)

    def set_nested(self, *keys_and_value: Any) -> None:
        *keys, value = keys_and_value
        if not keys or any(not isinstance(key, str) or not key for key in keys):
            raise ValueError("set_nested requires one or more non-empty string keys")
        detached = deepcopy(value)

        def mutate() -> None:
            node = self._config
            for key in keys[:-1]:
                if key not in node or not isinstance(node[key], dict):
                    node[key] = {}
                node = node[key]
            node[keys[-1]] = detached

        self._commit(mutate)

    def add_recent_file(self, path: str) -> None:
        normalized_path = os.fspath(path)

        def mutate() -> None:
            recent = self._config.get("recent_files", [])
            if not isinstance(recent, list):
                recent = []
            recent = [item for item in recent if item != normalized_path]
            recent.insert(0, normalized_path)
            self._config["recent_files"] = recent[:10]

        self._commit(mutate)

    def remove_recent_file(self, path: str) -> None:
        normalized_path = os.fspath(path)

        def mutate() -> None:
            recent = self._config.get("recent_files", [])
            if not isinstance(recent, list):
                recent = []
            self._config["recent_files"] = [
                item for item in recent if item != normalized_path
            ][:10]

        self._commit(mutate)

    def consume_reset_notice(self) -> bool:
        with self._lock:
            notice = self._reset_notice
            self._reset_notice = False
            return notice

    def _commit(self, mutator: Callable[[], None]) -> None:
        with self._lock:
            previous = deepcopy(self._config)
            try:
                mutator()
                self._deep_merge_missing(self._config, DEFAULT_CONFIG)
                self._normalize_schema()
                self._save_locked()
            except Exception:
                self._config = previous
                raise

    def save(self) -> None:
        with self._lock:
            self._normalize_schema()
            self._save_locked()

    def _save_locked(self) -> None:
        self._ensure_parent_dir()
        parent = os.path.dirname(self.path) or os.curdir
        prefix = f".{os.path.basename(self.path)}."
        encoded = (
            json.dumps(
                self._config,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        if len(encoded) > MAX_CONFIG_BYTES:
            raise ValueError(
                f"Configuration exceeds the {MAX_CONFIG_BYTES}-byte safety limit"
            )
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=prefix, suffix=".tmp", dir=parent
        )
        try:
            with os.fdopen(descriptor, "wb") as file:
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            try:
                os.chmod(temporary_path, 0o600)
            except OSError:
                pass
            os.replace(temporary_path, self.path)
            _fsync_directory(parent)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise
