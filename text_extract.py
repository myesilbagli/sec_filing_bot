"""
Extract plain text from SEC document bytes (HTML or TXT).
"""


def _parser() -> str:
    """Use lxml if available, else html.parser."""
    try:
        import lxml  # noqa: F401
        return "lxml"
    except ImportError:
        return "html.parser"


def extract_text(content: bytes, url: str) -> str:
    """
    Extract plain text from document bytes.
    - If url ends with .htm or .html: parse with BeautifulSoup, get_text(separator=" ").
    - Else: decode as utf-8 with errors="ignore".
    - Normalize whitespace: single spaces, no leading/trailing.
    """
    if not content:
        return ""
    url_lower = (url or "").lower()
    if url_lower.endswith(".htm") or url_lower.endswith(".html"):
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, _parser())
            text = soup.get_text(separator=" ")
        except Exception:
            text = content.decode("utf-8", errors="ignore")
    else:
        text = content.decode("utf-8", errors="ignore")
    return " ".join(text.split())
