"""Built-in review profiles and user-defined analysis guidance."""

from __future__ import annotations

import string
from typing import Dict, List

from config_manager import ConfigManager

ALLOWED_TEMPLATE_FIELDS = frozenset({"input_text", "style_name"})
MAX_GUIDANCE_CHARS = 32_000

DEFAULT_REVIEW_GUIDANCE = (
    "Review the text in its own detected language. Report clear spelling, grammar, "
    "word-choice, punctuation, capitalization, agreement, and malformed quote or "
    "bracket issues. Do not rewrite for personal style."
)

# A profile controls both local presentation and optional model guidance. Compiler
# formatting is generated locally from validated diagnostics, not trusted to the model.
BUILTIN_STYLES: Dict[str, str] = {
    "Python": DEFAULT_REVIEW_GUIDANCE,
    "Java": DEFAULT_REVIEW_GUIDANCE,
    "C++": DEFAULT_REVIEW_GUIDANCE,
}


def validate_guidance_template(template: str) -> str:
    """Validate a profile without permitting Python attribute/index traversal."""

    if not isinstance(template, str) or not template.strip():
        raise ValueError("Profile guidance cannot be empty")
    if len(template) > MAX_GUIDANCE_CHARS:
        raise ValueError(
            f"Profile guidance cannot exceed {MAX_GUIDANCE_CHARS} characters"
        )
    try:
        parsed = tuple(string.Formatter().parse(template))
    except ValueError as error:
        raise ValueError(f"Invalid profile template: {error}") from error
    for _literal, field_name, format_spec, conversion in parsed:
        if field_name is None:
            continue
        if field_name not in ALLOWED_TEMPLATE_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_TEMPLATE_FIELDS))
            raise ValueError(
                f"Unsupported profile placeholder {field_name!r}; allowed: {allowed}"
            )
        if conversion is not None or format_spec:
            raise ValueError("Profile placeholders cannot use conversions or formats")
    return template


def render_guidance_template(template: str, *, input_text: str, style_name: str) -> str:
    """Render an already constrained guidance template with inert placeholder data."""

    validate_guidance_template(template)
    return template.format_map(
        {
            "input_text": input_text,
            "style_name": style_name,
        }
    )


class StyleManager:
    def __init__(self, cfg: ConfigManager) -> None:
        self.cfg = cfg
        self.reload()

    @staticmethod
    def _sanitize_styles(data: object) -> Dict[str, str]:
        if not isinstance(data, dict):
            return {}
        sanitized: Dict[str, str] = {}
        for key, value in data.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            clean_name = key.strip()
            if (
                not clean_name
                or len(clean_name) > 100
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in clean_name
                )
            ):
                continue
            try:
                validate_guidance_template(value)
            except ValueError:
                continue
            sanitized[clean_name] = value
        return sanitized

    def reload(self) -> None:
        """Reload profiles from built-ins plus user overrides."""

        self._styles = BUILTIN_STYLES.copy()
        self._styles.update(self._sanitize_styles(self.cfg.get("styles", {}) or {}))

    @property
    def names(self) -> List[str]:
        return sorted(self._styles)

    def get(self, name: str) -> str:
        return self._styles.get(name, "")

    def set(self, name: str, template: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Profile name cannot be empty")
        if len(clean_name) > 100:
            raise ValueError("Profile name cannot exceed 100 characters")
        if any(
            ord(character) < 32 or ord(character) == 127 for character in clean_name
        ):
            raise ValueError("Profile name cannot contain control characters")
        validate_guidance_template(template)
        data = self._sanitize_styles(self.cfg.get("styles", {}) or {})
        data[clean_name] = template
        self.cfg.set("styles", data)
        self.reload()

    def delete(self, name: str) -> None:
        data = self._sanitize_styles(self.cfg.get("styles", {}) or {})
        data.pop(name, None)
        self.cfg.set("styles", data)
        self.reload()
