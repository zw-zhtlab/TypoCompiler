"""Validated language diagnostics and deterministic compiler-style renderers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

MAX_DIAGNOSTICS = 100
SEVERITIES = {"error", "warning", "info", "hint"}


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A one-based, source-bound language diagnostic."""

    line: int
    start_column: int
    end_column: int
    category: str
    severity: str
    message: str
    original: str = ""
    replacement: str = ""
    explanation: str = ""


@dataclass(frozen=True, slots=True)
class CompileResult:
    """The validated response returned by a language-analysis request."""

    language: str
    diagnostics: tuple[Diagnostic, ...]
    raw_response: str = ""

    @property
    def clean(self) -> bool:
        return not self.diagnostics


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _strip_code_fence(payload: str) -> str:
    text = payload.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        raise ValueError("Incomplete JSON code fence")
    return "\n".join(lines[1:-1]).strip()


def _required_string(item: dict[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Diagnostic field {name!r} must be a non-empty string")
    return value.strip()


def _optional_string(item: dict[str, Any], name: str) -> str:
    value = item.get(name, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"Diagnostic field {name!r} must be a string")
    return value.strip()


def _required_int(item: dict[str, Any], name: str) -> int:
    value = item.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Diagnostic field {name!r} must be an integer")
    return value


def _source_lines(source_text: str) -> list[str]:
    return source_text.split("\n") or [""]


def _parse_item(item: Any, lines: list[str]) -> Diagnostic:
    if not isinstance(item, dict):
        raise ValueError("Each diagnostic must be a JSON object")
    line = _required_int(item, "line")
    start = _required_int(item, "start_column")
    end = _required_int(item, "end_column")
    if line < 1 or line > len(lines):
        raise ValueError(f"Diagnostic line {line} is outside the input")
    line_length = len(lines[line - 1])
    if start < 1 or start > line_length + 1:
        raise ValueError(f"Diagnostic start column {start} is outside line {line}")
    if end < start or end > line_length + 1:
        raise ValueError(f"Diagnostic end column {end} is outside line {line}")

    severity = _required_string(item, "severity").lower()
    if severity not in SEVERITIES:
        raise ValueError(f"Unsupported diagnostic severity: {severity}")
    return Diagnostic(
        line=line,
        start_column=start,
        end_column=end,
        category=_required_string(item, "category"),
        severity=severity,
        message=_required_string(item, "message"),
        original=_optional_string(item, "original"),
        replacement=_optional_string(item, "replacement"),
        explanation=_optional_string(item, "explanation"),
    )


def parse_diagnostics(payload: str | dict[str, Any], source_text: str) -> CompileResult:
    """Parse and validate a JSON response against the exact analyzed source."""

    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    raw_response = payload if isinstance(payload, str) else json.dumps(payload)
    if isinstance(payload, str):
        text = _strip_code_fence(payload)
        if not text:
            raise ValueError("The model returned an empty response")
        try:
            data = json.loads(
                text,
                parse_constant=_reject_constant,
                object_pairs_hook=_reject_duplicate_keys,
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"The model response is not valid JSON: {error.msg}"
            ) from error
    elif isinstance(payload, dict):
        data = payload
    else:
        raise TypeError("payload must be a JSON string or object")

    if not isinstance(data, dict):
        raise ValueError("The model response must be a JSON object")
    language = data.get("language", "und")
    if not isinstance(language, str) or not language.strip():
        raise ValueError("Response field 'language' must be a non-empty string")
    items = data.get("diagnostics")
    if not isinstance(items, list):
        raise ValueError("Response field 'diagnostics' must be an array")
    if len(items) > MAX_DIAGNOSTICS:
        raise ValueError(f"Response has more than {MAX_DIAGNOSTICS} diagnostics")

    lines = _source_lines(source_text)
    parsed = [_parse_item(item, lines) for item in items]
    unique = {
        (
            diagnostic.line,
            diagnostic.start_column,
            diagnostic.end_column,
            diagnostic.severity,
            diagnostic.message,
        ): diagnostic
        for diagnostic in parsed
    }
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda diagnostic: (
                diagnostic.line,
                diagnostic.start_column,
                diagnostic.end_column,
                diagnostic.message.casefold(),
            ),
        )
    )
    return CompileResult(language.strip(), ordered, str(raw_response))


def _line_at(source_text: str, line: int) -> str:
    lines = _source_lines(source_text)
    return lines[line - 1]


def _caret(diagnostic: Diagnostic) -> str:
    width = max(1, diagnostic.end_column - diagnostic.start_column)
    return " " * (diagnostic.start_column - 1) + "^" + "~" * (width - 1)


def _render_python(diagnostics: Iterable[Diagnostic], source_text: str) -> str:
    blocks: list[str] = []
    for diagnostic in diagnostics:
        snippet = _line_at(source_text, diagnostic.line)
        blocks.append(
            "\n".join(
                (
                    f'  File "<input>", line {diagnostic.line}',
                    f"    {snippet}",
                    f"    {_caret(diagnostic)}",
                    f"LanguageError: {diagnostic.message}",
                )
            )
        )
    return "\n\n".join(blocks)


def _render_java(diagnostics: Iterable[Diagnostic], source_text: str) -> str:
    items = list(diagnostics)
    blocks = []
    for diagnostic in items:
        snippet = _line_at(source_text, diagnostic.line)
        blocks.append(
            "\n".join(
                (
                    f"Input.txt:{diagnostic.line}: error: {diagnostic.message}",
                    f"    {snippet}",
                    f"    {_caret(diagnostic)}",
                )
            )
        )
    noun = "error" if len(items) == 1 else "errors"
    blocks.append(f"{len(items)} {noun}")
    return "\n".join(blocks)


def _render_cpp(diagnostics: Iterable[Diagnostic], source_text: str) -> str:
    items = list(diagnostics)
    blocks = []
    for diagnostic in items:
        snippet = _line_at(source_text, diagnostic.line)
        blocks.append(
            "\n".join(
                (
                    f"input.txt:{diagnostic.line}:{diagnostic.start_column}: "
                    f"{diagnostic.severity}: {diagnostic.message}",
                    snippet,
                    _caret(diagnostic),
                )
            )
        )
    noun = "error" if len(items) == 1 else "errors"
    blocks.append(f"{len(items)} {noun} generated.")
    return "\n".join(blocks)


def render_diagnostics(style_name: str, result: CompileResult, source_text: str) -> str:
    """Render validated diagnostics locally, independent of model formatting."""

    if not result.diagnostics:
        return ""
    style = (style_name or "Python").casefold()
    if style == "java":
        return _render_java(result.diagnostics, source_text)
    if style in {"c++", "cpp", "cxx"}:
        return _render_cpp(result.diagnostics, source_text)
    return _render_python(result.diagnostics, source_text)
