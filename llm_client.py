# llm_client.py
import json
from typing import List, Dict, Tuple, Optional, Any
import urllib.request, urllib.error
from config_manager import ConfigManager
from styles import StyleManager, SUCCESS_SENTINEL

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'

class LLMClient:
    def __init__(self, cfg: ConfigManager, style_manager: StyleManager) -> None:
        self.cfg = cfg
        self.styles = style_manager

    def _get_cfg(self, overrides: Optional[Dict[str, Any]], *keys, default=None):
        if overrides is not None:
            node = overrides
            for k in keys:
                if not isinstance(node, dict) or k not in node:
                    break
                node = node[k]
            else:
                return node
        return self.cfg.get_nested(*keys, default=default)

    def _headers(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        api_key = self._get_cfg(overrides, "llm", "api_key", default="")
        header_name = self._get_cfg(overrides, "llm", "auth", "header_name", default="Authorization") or "Authorization"
        prefix = self._get_cfg(overrides, "llm", "auth", "prefix", default="Bearer ") or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers[header_name] = f"{prefix}{api_key}"
        return headers

    def _endpoint(self, overrides: Optional[Dict[str, Any]] = None) -> str:
        base = self._get_cfg(overrides, "llm", "base_url", default="https://api.openai.com/v1") or "https://api.openai.com/v1"
        return base.rstrip("/") + "/chat/completions"

    def _body(self, messages: List[Dict[str, str]], overrides: Optional[Dict[str, Any]] = None) -> Dict:
        model = self._get_cfg(overrides, "llm", "model", default="gpt-4o-mini")
        if not model:
            model = "gpt-4o-mini"
        temperature = self._get_cfg(overrides, "llm", "temperature", default=0.1)
        if temperature is None:
            temperature = 0.1
        max_tokens = self._get_cfg(overrides, "llm", "max_tokens", default=900)
        if max_tokens is None:
            max_tokens = 900
        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

    def test_connectivity(self, overrides: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        messages = [
            {"role": "system", "content": "Reply with a single word: pong"},
            {"role": "user", "content": "ping"},
        ]
        try:
            ok, text = self._request(messages, overrides=overrides)
            if not ok:
                return False, text
            return (text.strip().lower() == "pong"), text
        except Exception as e:
            return False, str(e)

    def generate_compiler_output(self, style_name: str, input_text: str) -> str:
        template = self.styles.get(style_name)
        if not template:
            raise RuntimeError(f"No template for style: {style_name}")
        system_prompt = (
            "You output ONLY the target compiler's diagnostics text for ENGLISH NATURAL-LANGUAGE TEXT. "
            "No markdown, no commentary. If nothing is wrong, emit the success token exactly."
        )
        # Use SafeDict to avoid KeyError for illustrative {{PLACEHOLDERS}} that authors forget to escape
        user_prompt = template.format_map(SafeDict(input_text=input_text, style_name=style_name))
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        ok, text = self._request(messages)
        if not ok:
            raise RuntimeError(text)
        content = (text or "").replace("\r\n", "\n").strip()
        if content.startswith("```"):
            c = content.strip("`")
            parts = c.split("\n", 1)
            content = (parts[1] if len(parts) > 1 else "").strip()
        if content == SUCCESS_SENTINEL:
            return ""
        return content

    def _request(self, messages: List[Dict[str, str]], overrides: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        data = json.dumps(self._body(messages, overrides=overrides)).encode("utf-8")
        req = urllib.request.Request(self._endpoint(overrides), data=data, headers=self._headers(overrides), method="POST")
        timeout = self._get_cfg(overrides, "llm", "timeout_seconds", default=60)
        if timeout is None:
            timeout = 60
        try:
            with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                payload = json.loads(raw)
                if "choices" in payload and payload["choices"]:
                    content = payload["choices"][0]["message"]["content"]
                    return True, content
                if "error" in payload:
                    return False, str(payload["error"])
                return False, raw
        except urllib.error.HTTPError as e:
            try:
                err = e.read().decode("utf-8", errors="ignore")
            except Exception:
                err = str(e)
            return False, f"HTTP {e.code}: {err}"
        except Exception as e:
            return False, str(e)
