def to_peer(value):
    """Normalize a recipient identifier coming from CSV (always strings) or
    from the parser (ints/strings) into something Pyrogram resolves correctly.

    A numeric id MUST be an int — Pyrogram treats a numeric *string* as a phone
    number and raises PeerIdInvalid. Usernames stay as strings.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.startswith("@"):
        return s
    if s.lstrip("-").isdigit():
        return int(s)
    return s
