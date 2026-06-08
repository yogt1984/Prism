"""Domain blocklist for source auto-discovery."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BLOCKLIST_PATH = Path("data/source_blocklist.txt")
_blocklist: set[str] | None = None


def load_blocklist(path: Path | None = None) -> set[str]:
    """Load blocked domains from file. Cached after first load."""
    global _blocklist
    if _blocklist is not None and path is None:
        return _blocklist

    p = path or _BLOCKLIST_PATH
    domains: set[str] = set()

    if not p.exists():
        logger.warning("Blocklist file not found: %s", p)
        _blocklist = domains
        return domains

    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Normalize: remove www. prefix, lowercase
        domain = line.lower().removeprefix("www.")
        domains.add(domain)

    _blocklist = domains
    logger.info("Loaded %d blocked domains", len(domains))
    return domains


def is_blocked(domain: str) -> bool:
    """Check if a domain is in the blocklist."""
    blocklist = load_blocklist()
    normalized = domain.lower().removeprefix("www.")
    # Check exact match and parent domain
    # e.g. "sports.yahoo.com" should match if "yahoo.com" is blocked
    parts = normalized.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in blocklist:
            return True
    return False


def reload_blocklist() -> set[str]:
    """Force reload from disk (after CLI edits)."""
    global _blocklist
    _blocklist = None
    return load_blocklist()
