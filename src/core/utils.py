import re

YES_RE = re.compile(r"^\s*(yes|y|ok|okay|confirm|submit|go ahead|sure)\s*[\.\!]*\s*$", re.I)

def last_user_text(messages):
    for m in reversed(messages or []):
        if m["role"] == "user":
            return m["content"]
    return ""

def looks_like_choice(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.isdigit() or len(t) <= 40
