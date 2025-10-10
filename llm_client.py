
# llm_client.py
import json
from typing import List, Dict, Tuple
import urllib.request, urllib.error
from config_manager import ConfigManager
from styles import StyleManager, SUCCESS_SENTINEL

class SafeDict(dict):
    """format_map 的安全字典：未知键保持原样（含花括号），避免 KeyError"""
    def __missing__(self, key):
        return '{' + key + '}'

class LLMClient:
    def __init__(self, cfg: ConfigManager, style_manager: StyleManager) -> None:
        self.cfg = cfg
        self.styles = style_manager

    def _headers(self) -> Dict[str, str]:
        api_key = self.cfg.get_nested("llm", "api_key", default="")
        header_name = self.cfg.get_nested("llm", "auth", "header_name", default="Authorization") or "Authorization"
        prefix = self.cfg.get_nested("llm", "auth", "prefix", default="Bearer ") or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers[header_name] = f"{prefix}{api_key}"
        return headers

    def _endpoint(self) -> str:
        base = self.cfg.get_nested("llm", "base_url", default="https://api.openai.com/v1") or "https://api.openai.com/v1"
        return base.rstrip("/") + "/chat/completions"

    def _body(self, messages: List[Dict[str, str]]) -> Dict:
        return {
            "model": self.cfg.get_nested("llm", "model", default="gpt-4o-mini") or "gpt-4o-mini",
            "messages": messages,
            "temperature": self.cfg.get_nested("llm", "temperature", default=0.1) or 0.1,
            "max_tokens": self.cfg.get_nested("llm", "max_tokens", default=900) or 900,
        }

    def test_connectivity(self) -> Tuple[bool, str]:
        messages = [
            {"role": "system", "content": "Reply with a single word: pong"},
            {"role": "user", "content": "ping"},
        ]
        try:
            ok, text = self._request(messages)
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

    def _request(self, messages: List[Dict[str, str]]) -> Tuple[bool, str]:
        data = json.dumps(self._body(messages)).encode("utf-8")
        req = urllib.request.Request(self._endpoint(), data=data, headers=self._headers(), method="POST")
        timeout = self.cfg.get_nested("llm", "timeout_seconds", default=60) or 60
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
