
# styles.py
from typing import Dict, List
from config_manager import ConfigManager

SUCCESS_SENTINEL = "__TC_OK__"

# Escape braces for examples with {{LIKE_THIS}} to avoid Python .format collisions.
BUILTIN_STYLES: Dict[str, str] = {
    "Python": (
        "You are a STRICT formatter that mimics CPython 3.11 interpreter diagnostics "
        "for ENGLISH NATURAL-LANGUAGE TEXT (not code).\n"
        f"SUCCESS CASE: If NO issues are found, reply with EXACTLY {SUCCESS_SENTINEL} and NOTHING ELSE.\n"
        "SCOPE of issues to flag as 'syntax': common misspellings; doubled/omitted words; missing terminal punctuation; "
        "comma splices/run-ons; subject–verb disagreement; inconsistent casing; malformed or mismatched quotes/brackets.\n"
        "OUTPUT CONTRACT:\n"
        " - Plain text only. NO markdown, NO code fences, NO explanations, NO suggestions.\n"
        " - For each issue (you may aggregate closely related ones), emit a CPython-like block:\n"
        "   Traceback (most recent call last):\\n"
        "     File \"<stdin>\", line {{LINE}}\\n"
        "       {{SNIPPET}}\\n"
        "       {{CARET}}\\n"
        "   SyntaxError: {{SHORT_MESSAGE}}\n"
        " - Use realistic line numbers from the input (1-based). Place the caret under the first offending token.\n"
        " - Keep {{SHORT_MESSAGE}} concise (<= 80 chars). Emit at most 8 blocks.\n"
        " - Do NOT add any extra lines before/after blocks.\n\n"
        "INPUT (<stdin>):\n{input_text}"
    ),
    "Java": (
        "You are a STRICT formatter that mimics javac (Java 17) diagnostics for ENGLISH NATURAL-LANGUAGE TEXT (not code).\n"
        f"SUCCESS CASE: If NO issues are found, reply with EXACTLY {SUCCESS_SENTINEL} and NOTHING ELSE.\n"
        "Treat each input line as a source line. Flag NL issues as syntax/lexical errors.\n"
        "OUTPUT CONTRACT:\n"
        " - Plain text only. NO markdown, NO explanations.\n"
        " - Emit concise diagnostics like:\n"
        "   Main.java:{{LINE}}: error: {{SHORT_MESSAGE}}\\n"
        "       {{SNIPPET}}\\n"
        "              ^\\n"
        "   {{OPTIONAL_NOTE}}\n"
        " - After all diagnostics, print a summary line: '1 error' or '{{N}} errors'.\n"
        " - Keep messages terse (<= 80 chars). Emit at most 8 errors.\n\n"
        "INPUT (Main.java):\n{input_text}"
    ),
    "C++": (
        "You are a STRICT formatter that mimics clang++/g++ (C++17) diagnostics for ENGLISH NATURAL-LANGUAGE TEXT (not code).\n"
        f"SUCCESS CASE: If NO issues are found, reply with EXACTLY {SUCCESS_SENTINEL} and NOTHING ELSE.\n"
        "Treat each input line as if it were source. Map NL issues to syntax/lexical errors.\n"
        "OUTPUT CONTRACT:\n"
        " - Plain text only. NO markdown, NO explanations.\n"
        " - Emit diagnostics like:\n"
        "   main.cpp:{{LINE}}:{{COLUMN}}: error: {{SHORT_MESSAGE}}\\n"
        "   {{SNIPPET}}\\n"
        "           ^\n"
        " - Finish with '1 error generated.' or '{{N}} errors generated.'\n"
        " - Choose COLUMN as the first character index (1-based) of the offending token. Max 8 errors; each message <= 80 chars.\n\n"
        "INPUT (main.cpp):\n{input_text}"
    ),
}

class StyleManager:
    def __init__(self, cfg: ConfigManager) -> None:
        self.cfg = cfg
        self.reload()

    @staticmethod
    def _sanitize_styles(data) -> Dict[str, str]:
        if not isinstance(data, dict):
            return {}
        clean: Dict[str, str] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str):
                clean[k] = v
        return clean

    def reload(self) -> None:
        """Reload styles from built-ins plus user overrides."""
        self._styles = BUILTIN_STYLES.copy()
        user_styles = self._sanitize_styles(self.cfg.get("styles", {}) or {})
        self._styles.update(user_styles)

    @property
    def names(self) -> List[str]:
        return sorted(self._styles.keys())

    def get(self, name: str) -> str:
        return self._styles.get(name, "")

    def set(self, name: str, template: str) -> None:
        self._styles[name] = template
        data = self._sanitize_styles(self.cfg.get("styles", {}) or {})
        data[name] = template
        self.cfg.set("styles", data)

    def delete(self, name: str) -> None:
        data = self._sanitize_styles(self.cfg.get("styles", {}) or {})
        if name in data:
            del data[name]
            self.cfg.set("styles", data)
        if name not in BUILTIN_STYLES and name in self._styles:
            del self._styles[name]
        # Reload to restore built-ins and apply remaining overrides.
        self.reload()
