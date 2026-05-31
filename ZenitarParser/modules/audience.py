"""Pure list operations over parsed audiences (list[dict] rows).

CSV always yields string values, so booleans arrive as 'True'/'False'/'1'.
These helpers are side-effect free and unit-testable.
"""
from typing import List


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "да")


def _ident(u: dict) -> str:
    """Stable identity for dedupe/subtract: prefer numeric id, else @username."""
    uid = str(u.get("id", "")).strip()
    if uid and uid not in ("0", "None", ""):
        return f"id:{uid}"
    un = str(u.get("username", "")).strip().lstrip("@").lower()
    return f"un:{un}" if un else ""


def dedupe(users: List[dict]) -> List[dict]:
    seen, out = set(), []
    for u in users:
        key = _ident(u)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def merge(*lists: List[dict]) -> List[dict]:
    combined = []
    for lst in lists:
        combined.extend(lst or [])
    return dedupe(combined)


def subtract(base: List[dict], exclude: List[dict]) -> List[dict]:
    """Everyone in `base` who is NOT in `exclude` (by id or username)."""
    ban = {_ident(u) for u in exclude if _ident(u)}
    return [u for u in dedupe(base) if _ident(u) not in ban]


def intersect(a: List[dict], b: List[dict]) -> List[dict]:
    keys_b = {_ident(u) for u in b if _ident(u)}
    return [u for u in dedupe(a) if _ident(u) in keys_b]


def apply_filter(users: List[dict], mode: str) -> List[dict]:
    if mode == "only_username":
        return [u for u in users if str(u.get("username", "")).strip()]
    if mode == "only_premium":
        return [u for u in users if _truthy(u.get("is_premium"))]
    if mode == "no_bots":
        return [u for u in users if not _truthy(u.get("is_bot"))]
    if mode == "only_humans":
        # drop bots and "deleted" accounts (no name and no username)
        out = []
        for u in users:
            if _truthy(u.get("is_bot")):
                continue
            if not str(u.get("first_name", "")).strip() and not str(u.get("username", "")).strip():
                continue
            out.append(u)
        return out
    return users
