# file_ops.py
import os

def read_text_utf8(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_text_utf8(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
