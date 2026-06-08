"""Tests for 06_02: Domain blocklist loading and matching."""

from pathlib import Path

import prism.agents.blocklist as bl_mod
from prism.agents.blocklist import is_blocked, load_blocklist, reload_blocklist


def _reset():
    bl_mod._blocklist = None


# ── load_blocklist ─────────────────────────────────────────────────


def test_load_blocklist_from_file(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("# comment\nreddit.com\n\ntwitter.com\n")
    domains = load_blocklist(f)
    assert domains == {"reddit.com", "twitter.com"}
    _reset()


def test_load_blocklist_ignores_comments_and_blanks(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("# social\nreddit.com\n\n# blog\nmedium.com\n  \n")
    domains = load_blocklist(f)
    assert "reddit.com" in domains
    assert "medium.com" in domains
    assert len(domains) == 2
    _reset()


def test_load_blocklist_normalizes_www(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("www.reddit.com\n")
    domains = load_blocklist(f)
    assert "reddit.com" in domains
    assert "www.reddit.com" not in domains
    _reset()


def test_load_blocklist_missing_file(tmp_path):
    _reset()
    domains = load_blocklist(tmp_path / "nonexistent.txt")
    assert domains == set()
    _reset()


def test_load_blocklist_caches():
    _reset()
    bl_mod._blocklist = {"cached.com"}
    domains = load_blocklist()  # no path → use cache
    assert domains == {"cached.com"}
    _reset()


def test_reload_blocklist(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("old.com\n")
    load_blocklist(f)

    # Modify file
    f.write_text("new.com\n")
    # Cache still returns old
    domains = load_blocklist(f)
    # But reload forces re-read
    bl_mod._BLOCKLIST_PATH = f
    domains = reload_blocklist()
    assert "new.com" in domains
    _reset()
    bl_mod._BLOCKLIST_PATH = Path("data/source_blocklist.txt")


# ── is_blocked ─────────────────────────────────────────────────────


def test_is_blocked_exact_match(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("reddit.com\ntwitter.com\n")
    load_blocklist(f)
    assert is_blocked("reddit.com") is True
    assert is_blocked("twitter.com") is True
    assert is_blocked("reuters.com") is False
    _reset()


def test_is_blocked_subdomain(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("yahoo.com\nreddit.com\n")
    load_blocklist(f)
    assert is_blocked("sports.yahoo.com") is True
    assert is_blocked("news.yahoo.com") is True
    assert is_blocked("bbc.co.uk") is False
    _reset()


def test_is_blocked_www_prefix(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("reddit.com\n")
    load_blocklist(f)
    assert is_blocked("www.reddit.com") is True
    _reset()


def test_is_blocked_case_insensitive(tmp_path):
    _reset()
    f = tmp_path / "blocklist.txt"
    f.write_text("Reddit.com\n")
    load_blocklist(f)
    assert is_blocked("REDDIT.COM") is True
    assert is_blocked("reddit.com") is True
    _reset()
