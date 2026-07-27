"""Minimal OpenAI-compatible client with strict request and response boundaries."""

from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Tuple

from config_manager import ConfigManager
from diagnostics import CompileResult, parse_diagnostics, render_diagnostics
from styles import StyleManager, render_guidance_template

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ERROR_BYTES = 64 * 1024
MAX_ANALYSIS_BYTES = 2 * 1024 * 1024
MAX_ERROR_DISPLAY_CHARS = 2_048
MAX_TIMEOUT_SECONDS = 3_600
READ_CHUNK_BYTES = 64 * 1024
TOKEN_PARAMETERS = frozenset({"max_tokens", "max_completion_tokens"})
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_RESERVED_AUTH_HEADERS = frozenset(
    {
        "accept",
        "connection",
        "content-length",
        "content-type",
        "expect",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never replay a credential-bearing request at a server-chosen URL."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


@dataclass(frozen=True)
class RequestSnapshot:
    """The complete immutable wire request captured before network IO starts."""

    endpoint: str
    headers: Mapping[str, str] = field(repr=False)
    body: bytes = field(repr=False)
    timeout: float
    sensitive_values: tuple[str, ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class AnalysisRequest:
    """Source context plus the immutable wire request captured by the UI thread."""

    style_name: str
    source_text: str = field(repr=False)
    request_snapshot: RequestSnapshot = field(repr=False)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


def _deep_merge(target: Dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = _thaw(value)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


class LLMClient:
    def __init__(self, cfg: ConfigManager, style_manager: StyleManager) -> None:
        self.cfg = cfg
        self.styles = style_manager

    def _configuration_snapshot(
        self, overrides: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        base = _thaw(self.cfg.snapshot())
        if overrides is not None:
            if not isinstance(overrides, Mapping):
                raise ValueError("LLM setting overrides must be a mapping")
            _deep_merge(base, overrides)
        return _freeze(base)

    @staticmethod
    def _value(snapshot: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        node: Any = snapshot
        for key in keys:
            if not isinstance(node, Mapping) or key not in node:
                return default
            node = node[key]
        return node

    @staticmethod
    def _endpoint_from(snapshot: Mapping[str, Any]) -> str:
        raw = LLMClient._value(snapshot, "llm", "base_url", default="")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("LLM base URL is required; no implicit endpoint is used")
        base_url = raw.strip()
        decoded_url = urllib.parse.unquote(base_url)
        if any(
            character.isspace() or unicodedata.category(character) == "Cc"
            for character in decoded_url
        ):
            raise ValueError("LLM base URL contains whitespace or a control character")
        try:
            parts = urllib.parse.urlsplit(base_url)
            # Accessing port also validates malformed or out-of-range port text.
            parts.port
        except ValueError as error:
            raise ValueError(f"Invalid LLM base URL: {error}") from error
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError("LLM base URL must use http or https")
        if not parts.hostname:
            raise ValueError("LLM base URL must include a host")
        if parts.username is not None or parts.password is not None:
            raise ValueError("Credentials are not allowed inside the LLM base URL")
        if parts.query or parts.fragment or "?" in base_url or "#" in base_url:
            raise ValueError("LLM base URL must not contain a query or fragment")
        hostname = parts.hostname.casefold()
        if scheme == "http" and hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(
                "Remote LLM endpoints must use HTTPS; HTTP is allowed only for "
                "localhost, 127.0.0.1, or ::1"
            )
        path = parts.path.rstrip("/")
        if not path.endswith("/chat/completions"):
            path += "/chat/completions"
        return urllib.parse.urlunsplit((scheme, parts.netloc, path, "", ""))

    @staticmethod
    def _headers_and_sensitive_from(
        snapshot: Mapping[str, Any],
    ) -> tuple[Dict[str, str], tuple[str, ...]]:
        api_key = LLMClient._value(snapshot, "llm", "api_key", default="")
        if not isinstance(api_key, str):
            raise ValueError("LLM API key must be text")
        # An environment secret avoids writing a key to config.json at all.
        api_key = api_key or os.environ.get("TYPOCOMPILER_API_KEY", "")
        header_name = LLMClient._value(
            snapshot, "llm", "auth", "header_name", default="Authorization"
        )
        prefix = LLMClient._value(snapshot, "llm", "auth", "prefix", default="Bearer ")
        if not isinstance(header_name, str) or not header_name:
            header_name = "Authorization"
        if not _HEADER_NAME.fullmatch(header_name):
            raise ValueError("Invalid LLM authentication header name")
        if header_name.casefold() in _RESERVED_AUTH_HEADERS:
            raise ValueError(
                "LLM authentication cannot use a reserved HTTP transport header"
            )
        if not isinstance(prefix, str):
            raise ValueError("LLM authentication prefix must be text")
        if any(
            unicodedata.category(character) == "Cc" for character in api_key + prefix
        ):
            raise ValueError("LLM authentication values contain a control character")
        if len(header_name) > 256 or len(prefix) + len(api_key) > 65_536:
            raise ValueError("LLM authentication header exceeds the safety limit")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key:
            headers[header_name] = f"{prefix}{api_key}"
        return headers, ((api_key,) if api_key else ())

    @staticmethod
    def _headers_from(snapshot: Mapping[str, Any]) -> Dict[str, str]:
        headers, _sensitive_values = LLMClient._headers_and_sensitive_from(snapshot)
        return headers

    @staticmethod
    def _body_from(
        snapshot: Mapping[str, Any], messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        model = LLMClient._value(snapshot, "llm", "model", default="")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("LLM model is required")
        temperature_raw = LLMClient._value(snapshot, "llm", "temperature", default=0.1)
        if isinstance(temperature_raw, bool):
            raise ValueError("LLM temperature must be a finite number from 0 to 2")
        try:
            temperature = float(temperature_raw)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError(
                "LLM temperature must be a finite number from 0 to 2"
            ) from error
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("LLM temperature must be a finite number from 0 to 2")

        max_tokens_raw = LLMClient._value(snapshot, "llm", "max_tokens", default=900)
        if isinstance(max_tokens_raw, bool):
            raise ValueError("LLM max tokens must be a positive integer")
        if isinstance(max_tokens_raw, float) and not max_tokens_raw.is_integer():
            raise ValueError("LLM max tokens must be a positive integer")
        try:
            max_tokens = int(max_tokens_raw)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("LLM max tokens must be a positive integer") from error
        if max_tokens <= 0 or max_tokens > 1_000_000:
            raise ValueError("LLM max tokens must be a positive integer")
        token_parameter = LLMClient._value(
            snapshot, "llm", "token_parameter", default="max_tokens"
        )
        if token_parameter not in TOKEN_PARAMETERS:
            allowed = ", ".join(sorted(TOKEN_PARAMETERS))
            raise ValueError(f"LLM token parameter must be one of: {allowed}")

        clean_messages: List[Dict[str, str]] = []
        for message in messages:
            if not isinstance(message, Mapping):
                raise ValueError("Each LLM message must be a mapping")
            role = message.get("role")
            content = message.get("content")
            if not isinstance(role, str) or not role:
                raise ValueError("Each LLM message requires a role")
            if not isinstance(content, str):
                raise ValueError("Each LLM message requires text content")
            clean_messages.append({"role": role, "content": content})
        body = {
            "model": model.strip(),
            "messages": clean_messages,
            "temperature": temperature,
        }
        body[token_parameter] = max_tokens
        return body

    @staticmethod
    def _timeout_from(snapshot: Mapping[str, Any]) -> float:
        raw = LLMClient._value(snapshot, "llm", "timeout_seconds", default=60)
        if isinstance(raw, bool):
            raise ValueError("LLM timeout must be a positive finite number")
        try:
            timeout = float(raw)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("LLM timeout must be a positive finite number") from error
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
            raise ValueError(
                f"LLM timeout must be between 0 and {MAX_TIMEOUT_SECONDS} seconds"
            )
        return timeout

    def _build_request_snapshot(
        self,
        messages: List[Dict[str, str]],
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> RequestSnapshot:
        config_snapshot = self._configuration_snapshot(overrides)
        body = self._body_from(config_snapshot, messages)
        encoded = json.dumps(
            body,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers, sensitive_values = self._headers_and_sensitive_from(config_snapshot)
        return RequestSnapshot(
            endpoint=self._endpoint_from(config_snapshot),
            headers=MappingProxyType(headers),
            body=encoded,
            timeout=self._timeout_from(config_snapshot),
            sensitive_values=sensitive_values,
        )

    def validate_overrides(self, overrides: Mapping[str, Any]) -> None:
        """Validate settings using the same path as a real request, without IO."""
        self._build_request_snapshot([], overrides=overrides)

    def _headers(self, overrides: Optional[Mapping[str, Any]] = None) -> Dict[str, str]:
        return self._headers_from(self._configuration_snapshot(overrides))

    def _endpoint(self, overrides: Optional[Mapping[str, Any]] = None) -> str:
        return self._endpoint_from(self._configuration_snapshot(overrides))

    def _body(
        self,
        messages: List[Dict[str, str]],
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._body_from(self._configuration_snapshot(overrides), messages)

    @staticmethod
    def _normalize_token(text: str) -> str:
        token = (text or "").strip()
        token = token.strip("`'\"")
        token = token.rstrip(".!;:,")
        return token.strip().upper()

    def _is_connectivity_pong(self, text: str) -> bool:
        return self._normalize_token(text) == "PONG"

    def test_connectivity(
        self, overrides: Optional[Mapping[str, Any]] = None
    ) -> Tuple[bool, str]:
        """Compatibility wrapper for synchronous callers."""

        try:
            snapshot = self.prepare_connectivity(overrides=overrides)
        except Exception as error:
            return False, str(error)
        return self.run_connectivity(snapshot)

    def prepare_connectivity(
        self, overrides: Optional[Mapping[str, Any]] = None
    ) -> RequestSnapshot:
        """Validate and freeze a connectivity check before background IO."""

        messages = [
            {"role": "system", "content": "Reply with a single word: pong"},
            {"role": "user", "content": "ping"},
        ]
        return self._build_request_snapshot(messages, overrides=overrides)

    def run_connectivity(self, snapshot: RequestSnapshot) -> Tuple[bool, str]:
        if not isinstance(snapshot, RequestSnapshot):
            raise TypeError("snapshot must be a RequestSnapshot")
        try:
            ok, text = self._send_snapshot(snapshot)
            if not ok:
                return False, text
            return self._is_connectivity_pong(text), text
        except Exception as error:
            return False, str(error)

    def prepare_analysis(self, style_name: str, input_text: str) -> AnalysisRequest:
        """Validate and freeze one structured analysis before background IO."""

        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError("Input text cannot be empty")
        try:
            input_bytes = len(input_text.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise ValueError("Input text contains invalid Unicode") from error
        if input_bytes > MAX_ANALYSIS_BYTES:
            raise ValueError(
                f"Input text exceeds the {MAX_ANALYSIS_BYTES}-byte analysis limit"
            )
        guidance = self.styles.get(style_name)
        if not guidance:
            raise ValueError(f"No analysis profile named {style_name!r}")
        guidance = render_guidance_template(
            guidance,
            input_text="[supplied separately]",
            style_name=style_name,
        )
        system_prompt = (
            "Analyze natural-language text in whatever language it uses. Return ONLY "
            "one JSON object with keys 'language' and 'diagnostics'. 'language' is a "
            "BCP-47 language tag. 'diagnostics' is an array; each item has integer "
            "line, start_column, end_column (1-based, end-exclusive), and string "
            "category, severity, message, original, replacement, explanation. "
            "severity must be error, warning, info, or hint. Every location must point "
            "inside the supplied text. Return an empty diagnostics array when no clear "
            "issue exists. Do not use markdown. Preserve the input language in messages "
            "and replacements."
        )
        user_prompt = json.dumps(
            {"review_guidance": guidance, "input_text": input_text},
            ensure_ascii=False,
            allow_nan=False,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        snapshot = self._build_request_snapshot(messages)
        return AnalysisRequest(style_name, input_text, snapshot)

    def run_analysis(self, request: AnalysisRequest) -> CompileResult:
        """Execute a previously frozen request and validate its source coordinates."""

        if not isinstance(request, AnalysisRequest):
            raise TypeError("request must be an AnalysisRequest")
        ok, text = self._send_snapshot(request.request_snapshot)
        if not ok:
            raise RuntimeError(text)
        return parse_diagnostics(text, request.source_text)

    def analyze(self, style_name: str, input_text: str) -> CompileResult:
        return self.run_analysis(self.prepare_analysis(style_name, input_text))

    def generate_compiler_output(self, style_name: str, input_text: str) -> str:
        """Compatibility API returning locally rendered validated diagnostics."""

        result = self.analyze(style_name, input_text)
        return render_diagnostics(style_name, result, input_text)

    @staticmethod
    def _set_response_timeout(response, timeout: float) -> None:
        """Best-effort update of urllib's underlying socket timeout."""

        file_pointer = getattr(response, "fp", None)
        raw = getattr(file_pointer, "raw", None)
        sock = getattr(raw, "_sock", None) or getattr(file_pointer, "_sock", None)
        if sock is not None and hasattr(sock, "settimeout"):
            sock.settimeout(max(0.001, timeout))

    @staticmethod
    def _read_limited(response, limit: int, *, deadline: float | None = None) -> bytes:
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > limit:
                    raise ValueError(f"LLM response exceeds the {limit}-byte limit")
            except ValueError as error:
                if "exceeds" in str(error):
                    raise
                # A malformed Content-Length cannot bypass the actual bounded read.
        chunks: list[bytes] = []
        total = 0
        while total <= limit:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("LLM response exceeded the total timeout")
                LLMClient._set_response_timeout(response, remaining)
            max_chunk_size = min(READ_CHUNK_BYTES, limit + 1 - total)
            read_once = getattr(response, "read1", None)
            chunk = (
                read_once(max_chunk_size)
                if callable(read_once)
                else response.read(max_chunk_size)
            )
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > limit:
            raise ValueError(f"LLM response exceeds the {limit}-byte limit")
        return b"".join(chunks)

    @staticmethod
    def _safe_error_detail(detail: str, snapshot: RequestSnapshot | None = None) -> str:
        clean = "".join(
            " " if unicodedata.category(character) == "Cc" else character
            for character in detail
        )
        clean = " ".join(clean.split())
        if snapshot is not None:
            for value in snapshot.sensitive_values:
                if value:
                    clean = clean.replace(value, "[REDACTED]")
            for name, value in snapshot.headers.items():
                if name.casefold() in {"content-type", "accept"} or not value:
                    continue
                clean = clean.replace(value, "[REDACTED]")
        if len(clean) > MAX_ERROR_DISPLAY_CHARS:
            clean = clean[: MAX_ERROR_DISPLAY_CHARS - 1].rstrip() + "…"
        return clean

    @staticmethod
    def _parse_response(
        raw: bytes, snapshot: RequestSnapshot | None = None
    ) -> Tuple[bool, str]:
        if not raw or not raw.strip():
            return False, "Empty response body from LLM endpoint"
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            return False, f"LLM response is not valid UTF-8: {error}"
        try:
            payload = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
        except (json.JSONDecodeError, ValueError) as error:
            if isinstance(error, json.JSONDecodeError):
                detail = error.msg
            else:
                detail = str(error)
            return False, f"Invalid or truncated JSON response: {detail}"
        if not isinstance(payload, dict):
            return False, "LLM response must be a JSON object"
        if "error" in payload:
            detail = LLMClient._safe_error_detail(str(payload["error"]), snapshot)
            return False, f"LLM error: {detail}"
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return False, "LLM response is missing choices"
        choice = choices[0]
        if not isinstance(choice, dict):
            return False, "LLM response contains an invalid choice"
        finish_reason = choice.get("finish_reason")
        if finish_reason == "content_filter":
            return False, "LLM response was blocked by the content filter"
        if finish_reason is None:
            return False, "LLM response is missing a completion finish reason"
        if finish_reason != "stop":
            return False, f"LLM response was truncated (finish_reason={finish_reason})"
        message = choice.get("message")
        if not isinstance(message, dict):
            return False, "LLM response choice is missing a message"
        refusal = message.get("refusal")
        if refusal is not None:
            if not isinstance(refusal, str):
                return False, "LLM response contains an invalid refusal"
            if refusal.strip():
                detail = LLMClient._safe_error_detail(refusal, snapshot)
                return False, f"LLM refused the request: {detail}"
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return False, "LLM response message has empty or missing content"
        if snapshot is not None and any(
            value and value in content for value in snapshot.sensitive_values
        ):
            return False, "LLM response contained sensitive credential material"
        return True, content

    def _request(
        self,
        messages: List[Dict[str, str]],
        overrides: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[bool, str]:
        try:
            snapshot = self._build_request_snapshot(messages, overrides=overrides)
        except Exception as error:
            return False, str(error)
        return self._send_snapshot(snapshot)

    def _send_snapshot(self, snapshot: RequestSnapshot) -> Tuple[bool, str]:
        """Send an immutable request with redirect, size, and total-time bounds."""

        deadline = time.monotonic() + snapshot.timeout
        try:
            request = urllib.request.Request(
                snapshot.endpoint,
                data=snapshot.body,
                headers=dict(snapshot.headers),
                method="POST",
            )
            opener = urllib.request.build_opener(_NoRedirectHandler())
            with opener.open(request, timeout=snapshot.timeout) as response:
                raw = self._read_limited(
                    response, MAX_RESPONSE_BYTES, deadline=deadline
                )
            return self._parse_response(raw, snapshot)
        except urllib.error.HTTPError as error:
            if error.code in _REDIRECT_CODES:
                return (
                    False,
                    f"HTTP {error.code}: redirects are disabled for LLM requests",
                )
            try:
                raw_error = self._read_limited(
                    error, MAX_ERROR_BYTES, deadline=deadline
                )
                detail = self._safe_error_detail(
                    raw_error.decode("utf-8", errors="replace"),
                    snapshot,
                )
            except Exception:
                detail = self._safe_error_detail(
                    str(error.reason or error),
                    snapshot,
                )
            suffix = f": {detail}" if detail else ""
            return False, f"HTTP {error.code}{suffix}"
        except TimeoutError:
            return False, "LLM response exceeded the total timeout"
        except Exception as error:
            return False, self._safe_error_detail(str(error), snapshot)
