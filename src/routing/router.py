from typing import Optional, Tuple, List, Dict

def route_by_keywords(message: str, agents: List[Dict]) -> Tuple[Optional[str], int]:
    t = (message or "").lower()
    best_id, best_score = None, 0
    for a in agents:
        kws = a.get("keywords", []) or []
        score = sum(1 for kw in kws if kw.lower() in t)
        if score > best_score:
            best_id, best_score = a["agent_id"], score
    return (best_id, best_score) if best_score > 0 else (None, 0)

def parse_choice(text: str, agents: List[Dict]) -> Optional[str]:
    t = (text or "").strip().lower()
    if t.isdigit():
        i = int(t) - 1
        if 0 <= i < len(agents):
            return agents[i]["agent_id"]
    # match by name or agent_id
    for a in agents:
        if t == a["name"].lower() or t == a["agent_id"].lower():
            return a["agent_id"]
    return None
