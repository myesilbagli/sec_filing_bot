"""
Classify filing plain text into event types using regex phrase rules and confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Event type constants
PREF_CALL = "PREF_CALL"
PREF_PARTIAL_CALL = "PREF_PARTIAL_CALL"
PREF_NEW_ISSUE = "PREF_NEW_ISSUE"
DIV_SUSPENSION = "DIV_SUSPENSION"
OFFERING = "OFFERING"
RIGHTS_OFFERING = "RIGHTS_OFFERING"
TENDER_OFFER = "TENDER_OFFER"
EXCHANGE_OFFER = "EXCHANGE_OFFER"
CEF_DISTRIBUTION_CHANGE = "CEF_DISTRIBUTION_CHANGE"
LIQUIDATION_TERMINATION = "LIQUIDATION_TERMINATION"
EARNINGS = "EARNINGS"
GENERIC_NEWS = "GENERIC_NEWS"
NOT_RELEVANT = "NOT_RELEVANT"

# All classified event types (for feedback "Wrong" keyboard). Excludes NOT_RELEVANT (feedback sentinel only).
ALL_EVENT_TYPES = (
    PREF_CALL,
    PREF_PARTIAL_CALL,
    PREF_NEW_ISSUE,
    DIV_SUSPENSION,
    OFFERING,
    RIGHTS_OFFERING,
    TENDER_OFFER,
    EXCHANGE_OFFER,
    CEF_DISTRIBUTION_CHANGE,
    LIQUIDATION_TERMINATION,
    EARNINGS,
    GENERIC_NEWS,
)


@dataclass(frozen=True)
class EventRule:
    event_type: str
    patterns: list[str]  # regex patterns
    base: float = 0.30
    per_hit: float = 0.20
    cap: float = 1.00
    priority: int = 0


# Regex patterns per event type (case-insensitive). Keep them specific.
RULES: list[EventRule] = [
    EventRule(
        event_type=TENDER_OFFER,
        priority=100,
        patterns=[
            r"\btender offer\b",
            r"\boffer to purchase\b",
            r"\bcommencement of a tender offer\b",
            r"\bissuer tender offer\b",
            r"\bwithdrawal rights\b",
            r"\bexpiration date\b.*\btender\b",
        ],
    ),
    EventRule(
        event_type=EXCHANGE_OFFER,
        priority=95,
        patterns=[
            r"\boffer(?:s|ing)? to exchange\b",
            r"\bexchange offer\b",
            r"\bsolicitation of consents\b",
            r"\bconsent solicitation\b",
            r"\bnew notes?\b.*\bexchange\b",
        ],
    ),
    EventRule(
        event_type=PREF_PARTIAL_CALL,
        priority=90,
        patterns=[
            r"\bpartial redemption\b",
            r"\bpartially redeem\b",
            r"\bwill redeem\b.*\ba portion of\b",
            r"\baggregate liquidation preference\b.*\bof\b.*\bwill be redeemed\b",
        ],
    ),
    EventRule(
        event_type=PREF_CALL,
        priority=80,
        patterns=[
            r"\bnotice of redemption\b",
            r"\bcalled for redemption\b",
            r"\bwill redeem\b",
            r"\bredemption date\b",
            r"\boptional redemption\b",
            r"\bmandatory redemption\b",
            r"\bredemption price\b",
            r"\bredemption right\b",
            r"\baggregate liquidation preference\b.*\bredemption\b",
        ],
    ),
    EventRule(
        event_type=DIV_SUSPENSION,
        priority=70,
        patterns=[
            r"\bsuspend(?:ed|s|ing)?\b.*\bdividend",
            r"\bsuspension of (?:the )?dividend",
            r"\bom(?:it|itted)\b.*\bdividend",
            r"\bwill not declare\b.*\bdividend",
            r"\bcease\b.*\bpay(?:ing|ment)\b.*\bdividend",
            r"\bdividends?\b.*\bin arrears\b",
        ],
    ),
    EventRule(
        event_type=RIGHTS_OFFERING,
        priority=85,
        patterns=[
            r"\bright(s)? offering\b",
            r"\bsubscription rights\b",
            r"\btransferable rights\b",
            r"\bnon-?transferable rights\b",
            r"\bbasic subscription privilege\b",
            r"\bover-?subscription privilege\b",
            r"\bsubscription price\b",
        ],
    ),
    EventRule(
        event_type=OFFERING,
        priority=60,
        patterns=[
            r"\bprospectus supplement\b",
            r"\bunderwritten (?:public )?offering\b",
            r"\bat-the-market\b|\batm offering\b|\bsales agreement\b",
            r"\bshelf (?:registration|offering)\b",
            r"\boffering of\b",
            r"\bunderwriting agreement\b",
            r"\bplacement agent\b",
            r"\bregistered direct offering\b",
        ],
    ),
    EventRule(
        event_type=PREF_NEW_ISSUE,
        priority=65,
        patterns=[
            r"\bdepositary shares\b",
            r"\bpreferred stock\b",
            r"\bseries [a-z0-9]+\b.*\bpreferred\b",
            r"\bfixed[- ]to[- ]floating\b.*\bpreferred\b",
            r"\bliquidation preference\b.*\b\$?\d+\b",
            r"\brate reset\b.*\bpreferred\b",
        ],
    ),
    EventRule(
        event_type=CEF_DISTRIBUTION_CHANGE,
        priority=75,
        patterns=[
            r"\bmanaged distribution\b",
            r"\bdistribution policy\b",
            r"\bdistribution rate\b",
            r"\bmonthly distribution\b|\bquarterly distribution\b",
            r"\bcut\b.*\bdistribution\b",
            r"\breduc(?:e|ed|es|ing)\b.*\bdistribution\b",
            r"\bdistribution will\b.*\b(?:decrease|increase|change)\b",
            r"\bsuspend(?:ed|s|ing)?\b.*\bdistribution\b",
        ],
    ),
    EventRule(
        event_type=LIQUIDATION_TERMINATION,
        priority=78,
        patterns=[
            r"\bliquidation\b",
            r"\btermination date\b",
            r"\bwind(?:ing)?[- ]up\b",
            r"\bplan of liquidation\b",
            r"\bdissolution\b",
            r"\bconvert(?:ed|s|ing)\b.*\bto an open-?end\b",
        ],
    ),
    EventRule(
        event_type=EARNINGS,
        priority=72,
        patterns=[
            r"\bearnings release\b",
            r"\bquarterly earnings\b",
            r"\bannual earnings\b",
            r"\bearnings call\b",
            r"\bconference call\b.*\bearnings\b",
            r"\bannouncement of (?:quarterly |annual )?earnings\b",
            r"\bresults (?:for|of) the (?:quarter|fiscal|period)\b",
            r"\bearnings (?:for|report|results)\b",
            r"\bnet income\b.*\bquarter\b",
            r"\bfinancial results\b",
        ],
    ),
]


def _count_regex_hits(text: str, patterns: list[str]) -> int:
    """
    Count how many patterns match at least once (case-insensitive).
    Each pattern counts at most once.
    """
    if not text:
        return 0
    hits = 0
    for pat in patterns:
        try:
            if re.search(pat, text, flags=re.IGNORECASE):
                hits += 1
        except re.error:
            continue
    return hits


def _pattern_to_evidence_phrase(pat: str) -> str:
    """
    Derive a plain search phrase from a regex pattern for evidence snippet extraction.
    Removes \\b and takes the first literal segment (stops at . * ? ( ) etc.).
    """
    s = pat.replace(r"\b", "")
    out: list[str] = []
    for c in s:
        if c in ".*?()[]\\+{}|^$":
            break
        out.append(c)
    return "".join(out).strip()


def classify_event(plain_text: str) -> tuple[str, float]:
    """
    Returns (event_type, confidence). Confidence in [0, 1].
    Rule confidence: base + per_hit*(hits-1), capped. Tie broken by priority.
    """
    if not (plain_text and plain_text.strip()):
        return GENERIC_NEWS, 0.2

    best_type = GENERIC_NEWS
    best_conf = 0.2
    best_pri = -1

    for rule in RULES:
        hits = _count_regex_hits(plain_text, rule.patterns)
        if hits <= 0:
            continue

        conf = min(rule.cap, rule.base + rule.per_hit * max(0, hits - 1))

        if (conf > best_conf) or (conf == best_conf and rule.priority > best_pri):
            best_type = rule.event_type
            best_conf = conf
            best_pri = rule.priority

    return best_type, best_conf


def get_phrases_for_event(event_type: str) -> list[str]:
    """
    Return plain-string phrases for an event type (for evidence snippet extraction).
    Derived from regex patterns so evidence_snippets can use substring search.
    """
    for rule in RULES:
        if rule.event_type == event_type:
            phrases = [_pattern_to_evidence_phrase(p) for p in rule.patterns]
            return [p for p in phrases if p]
    return []


def event_type_display_name(event_type: str) -> str:
    """Human-readable label for Telegram."""
    labels = {
        PREF_CALL: "Redemption / Call",
        PREF_PARTIAL_CALL: "Partial call / Redemption",
        PREF_NEW_ISSUE: "New preferred issue / terms",
        DIV_SUSPENSION: "Dividend suspension / omission",
        OFFERING: "Offering / ATM",
        RIGHTS_OFFERING: "Rights offering",
        TENDER_OFFER: "Tender offer / repurchase",
        EXCHANGE_OFFER: "Exchange offer / consent",
        CEF_DISTRIBUTION_CHANGE: "CEF distribution change",
        LIQUIDATION_TERMINATION: "Liquidation / Termination",
        EARNINGS: "Earnings / earnings call",
        GENERIC_NEWS: "Filing",
    }
    return labels.get(event_type, event_type or "Filing")
