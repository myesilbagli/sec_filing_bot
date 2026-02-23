"""
Classify filing plain text into event types using phrase rules and confidence.
"""

# Event type constants
PREF_CALL = "PREF_CALL"
DIV_SUSPENSION = "DIV_SUSPENSION"
OFFERING = "OFFERING"
RIGHTS_OFFERING = "RIGHTS_OFFERING"
CEF_DISTRIBUTION_CHANGE = "CEF_DISTRIBUTION_CHANGE"
GENERIC_NEWS = "GENERIC_NEWS"

# Phrase lists per event type (case-insensitive match). Easy to extend.
EVENT_PHRASES: dict[str, list[str]] = {
    PREF_CALL: [
        "notice of redemption",
        "redemption of",
        "called for redemption",
        "redemption date",
        "call the",
        "optional redemption",
        "mandatory redemption",
        "redemption price",
        "redemption right",
    ],
    DIV_SUSPENSION: [
        "suspend",
        "suspension of dividend",
        "omit the dividend",
        "omit dividend",
        "dividend will not",
        "discontinue.*dividend",
        "cease paying",
    ],
    OFFERING: [
        "prospectus supplement",
        "underwritten offering",
        "at-the-market",
        "atm offering",
        "shelf offering",
        "offering of",
        "offered by",
        "underwriting agreement",
        "placement agent",
    ],
    RIGHTS_OFFERING: [
        "rights offering",
        "subscription rights",
        "transferable rights",
        "rights to purchase",
        "subscription offer",
    ],
    CEF_DISTRIBUTION_CHANGE: [
        "distribution policy",
        "managed distribution",
        "distribution rate",
        "cut.*distribution",
        "reduce.*distribution",
        "distribution will",
        "monthly distribution",
        "quarterly distribution",
    ],
}


def _count_matches(text: str, phrases: list[str]) -> int:
    """Case-insensitive phrase count in text. Each phrase counted at most once."""
    lower = text.lower()
    count = 0
    for p in phrases:
        if p.lower() in lower:
            count += 1
    return count


def classify_event(plain_text: str) -> tuple[str, float]:
    """
    Classify extracted filing text into an event type and confidence.
    Returns (event_type, confidence). Confidence in [0, 1]; multiple phrase
    matches increase confidence. Highest-scoring type wins; tie or none -> GENERIC_NEWS.
    """
    if not (plain_text or plain_text.strip()):
        return GENERIC_NEWS, 0.2

    scores: dict[str, float] = {}
    for event_type, phrases in EVENT_PHRASES.items():
        n = _count_matches(plain_text, phrases)
        if n > 0:
            # e.g. 0.3 + 0.2 * n, cap at 1.0
            scores[event_type] = min(1.0, 0.3 + 0.2 * n)

    if not scores:
        return GENERIC_NEWS, 0.2

    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]
    return best_type, confidence


def get_phrases_for_event(event_type: str) -> list[str]:
    """Return the phrase list for an event type (for evidence snippet extraction)."""
    return list(EVENT_PHRASES.get(event_type, []))


def event_type_display_name(event_type: str) -> str:
    """Human-readable label for Telegram."""
    labels = {
        PREF_CALL: "Redemption / Call",
        DIV_SUSPENSION: "Dividend suspension",
        OFFERING: "Offering",
        RIGHTS_OFFERING: "Rights offering",
        CEF_DISTRIBUTION_CHANGE: "CEF distribution change",
        GENERIC_NEWS: "Filing",
    }
    return labels.get(event_type, event_type or "Filing")
