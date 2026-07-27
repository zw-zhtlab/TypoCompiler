# TypoCompiler

**Languages:** [简体中文](./README.md) · **English** · [日本語](./README-ja.md) · [한국어](./README-ko.md) · [Español](./README-es.md) · [Deutsch](./README-de.md) · [Français](./README-fr.md)

TypoCompiler is a small desktop writing-review client that presents language issues like compiler diagnostics. You edit text, run one LLM analysis, inspect source-bound issues, and view Python-, Java-, or C++-style output in the same window.

## What changed in 2.1

- A single-window workspace replaces the extra run window.
- The editor, diagnostic list, and read-only compiler output are visible together.
- Double-clicking a diagnostic moves the caret to its source location; severity is shown as text as well as highlighting.
- Scrollbars, keyboard navigation, focusable controls, cursor position, stale-result notices, and run cancellation improve accessibility and clarity.
- The model returns structured JSON. TypoCompiler validates every line and column, then renders compiler output locally.
- Opened files retain their detected UTF-8 BOM and newline convention and are saved atomically.
- Worker threads return data through a main-thread queue; stale or post-close results cannot touch Tk or replace a newer run.
- Remote endpoints require HTTPS. Plain HTTP is accepted only for `localhost`, `127.0.0.1`, and `::1`.
- Packaging metadata and automated quality/package CI are included.

## Requirements and launch

- Python 3.10 or newer
- Tkinter (included with the standard Windows and macOS Python installers; some Linux distributions package it as `python3-tk`)
- An OpenAI-compatible chat-completions endpoint and model

There are no third-party runtime Python dependencies.

```bash
python typocompiler.py
# equivalent module entry
python -m typocompiler
```

Or install the local command:

```bash
python -m pip install .
typocompiler
```

The installed `typocompiler` entry is a GUI script, so Windows does not open an extra console. Open **Settings → LLM Settings**, enter the base URL, model, and optional credential, then use **F5** to analyze the editor text. The configured base URL is extended with `/chat/completions`.

## Keyboard workflow

| Action | Shortcut |
| --- | --- |
| New / Open / Save | `Ctrl+N` / `Ctrl+O` / `Ctrl+S` |
| Save As | `Ctrl+Shift+S` |
| Run analysis | `F5` |
| Cancel or disregard the active run | `Esc` |
| Copy compiler output | `Ctrl+Shift+C` |
| Increase / decrease / reset font | `Ctrl++` / `Ctrl+-` / `Ctrl+0` |

Cancelling cannot terminate an HTTP call already in progress, but its eventual response is ignored. If the text changes during a run, results remain visible and are clearly marked as belonging to an earlier snapshot.

## Diagnostics and profiles

The model identifies the input language and returns a JSON diagnostic list. Each item must contain a valid source line, start/end column, severity, category, and message; original text, replacement, and explanation are optional. Invalid or out-of-range responses are rejected instead of being displayed as trustworthy output.

Python, Java, and C++ are presentation styles applied locally to the same validated result. **Settings → Manage Styles** changes review guidance; it does not execute code or install a compiler. Results still depend on the configured model and are not guaranteed to find every language issue.

Custom guidance accepts only the inert placeholders `{input_text}` and `{style_name}`. Empty or malformed templates, unknown fields, attribute access, indexing, conversions, and format specifications are rejected before persistence. Analysis always produces one canonical diagnostic set; changing the display style only re-renders that set locally.

## Files, privacy, and configuration

- Text and Markdown files up to 16 MiB can be opened; one UTF-8 analysis payload is limited to 2 MiB to bound UI work and provider cost.
- Each analysis sends the current text and review guidance to the configured provider. Do not submit sensitive text unless that provider is appropriate for it.
- The settings dialog explicitly chooses between `TYPOCOMPILER_API_KEY` (no local key) and local plain-text storage in `~/.typocompiler/config.json`. Prefer a scoped token and the environment option.
- A malformed configuration is moved to a unique, best-effort owner-only `config.json.broken-*` backup before defaults are written. Existing backups are never deliberately overwritten.
- Remote HTTP URLs, URL credentials, query strings, fragments, whitespace, and control characters are rejected. Redirects are disabled, response/error bodies are bounded, and response reading observes a total deadline.
- The output-token field is selectable: `max_tokens` remains the compatibility default, while `max_completion_tokens` is available for providers and models that require it.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
python -m pip wheel . --no-deps -w dist-test
```

GitHub Actions runs Ruff, formatting, wheel construction, and an import smoke check.

Licensed under the [MIT License](./LICENSE).
