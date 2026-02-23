"""
Extract short evidence snippets from plain text around matched phrases.
"""


def extract_snippets(
    plain_text: str,
    phrases: list[str],
    window_chars: int = 250,
    max_snippets: int = 3,
    max_snippet_len: int = 200,
) -> list[str]:
    """
    For each phrase, find first occurrence (case-insensitive), take a window of
    window_chars before/after, clean (normalize whitespace), truncate to max_snippet_len.
    Return at most max_snippets unique snippets (by phrase order; avoid duplicate spans).
    """
    if not plain_text or not phrases:
        return []

    lower = plain_text.lower()
    normalized = " ".join(plain_text.split())
    lower_norm = " ".join(lower.split())
    seen_starts: set[int] = set()
    snippets: list[str] = []

    for phrase in phrases:
        if len(snippets) >= max_snippets:
            break
        p_lower = phrase.lower()
        idx = lower_norm.find(p_lower)
        if idx < 0:
            continue
        # Avoid returning same span twice (approximate: same start)
        if idx in seen_starts:
            continue
        seen_starts.add(idx)

        start = max(0, idx - window_chars)
        end = min(len(normalized), idx + len(phrase) + window_chars)
        snip = normalized[start:end].strip()
        snip = " ".join(snip.split())
        if len(snip) > max_snippet_len:
            snip = snip[: max_snippet_len - 3] + "..."
        if not snip:
            continue
        if snip not in snippets:
            snippets.append(snip)

    return snippets[:max_snippets]
