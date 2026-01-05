import re
from typing import Any, Dict, List, Tuple

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

def _strip_md_bold(s: str) -> str:
    return BOLD_RE.sub(r"\1", s)

def parse_assistant_message(raw: str) -> Dict[str, Any]:
    """
    Converts simple markdown-ish assistant messages into UI-friendly blocks.
    Supports:
      - first line as title (if short)
      - subsequent lines as paragraphs
      - "I’ll need: **a, b, c**." => bullets
    """
    raw = (raw or "").strip()
    if not raw:
        return {"text": "", "blocks": []}

    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    title = None
    blocks: List[Dict[str, Any]] = []

    # Title heuristic: first line ends with "." or "!" or "?" and is short-ish
    if lines and len(lines[0]) <= 80:
        title = _strip_md_bold(lines[0])
        lines = lines[1:]

    need_items: List[str] = []
    rest_lines: List[str] = []

    for l in lines:
        # Detect "I’ll need: **a, b, c**"
        if "need" in l.lower() and ":" in l:
            # grab content after colon and strip bold
            after = l.split(":", 1)[1].strip()
            after = _strip_md_bold(after)
            # remove trailing punctuation
            after = after.rstrip(".")
            # split commas
            items = [x.strip() for x in after.split(",") if x.strip()]
            if items:
                need_items.extend(items)
                continue
        rest_lines.append(l)

    if title:
        blocks.append({"type": "title", "text": title})

    if need_items:
        blocks.append({"type": "bullets", "title": "Details needed", "items": need_items})

    # Remaining lines become paragraphs (combine if multiple)
    if rest_lines:
        blocks.append({"type": "text", "text": _strip_md_bold(" ".join(rest_lines))})

    # Always include raw for fallback rendering
    return {"text": raw, "blocks": blocks}
