# file_ops.py
import os
import locale

def read_text_utf8(path: str) -> str:
    encodings = ["utf-8", "utf-8-sig", locale.getpreferredencoding(False), "gb18030"]
    last_error = None
    seen = set()
    for enc in encodings:
        if not enc or enc in seen:
            continue
        seen.add(enc)
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError as e:
            last_error = e
    if last_error is not None:
        raise last_error
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_text_utf8(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
