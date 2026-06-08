"""Tests for 06_03: RSS feed detection."""

from unittest.mock import MagicMock, patch

import httpx

from prism.agents.rss_detect import (
    _COMMON_PATHS,
    _looks_like_feed,
    _parse_homepage_links,
    _probe_common_paths,
    detect_rss_feed,
)


# ── _looks_like_feed heuristic ─────────────────────────────────────


def test_looks_like_feed_rss():
    assert _looks_like_feed('<?xml version="1.0"?><rss><channel><item>x</item></channel></rss>')


def test_looks_like_feed_atom():
    assert _looks_like_feed('<feed xmlns="http://www.w3.org/2005/Atom"><entry>x</entry></feed>')


def test_looks_like_feed_rdf():
    assert _looks_like_feed('<rdf:RDF><channel>x</channel><item>x</item></rdf:RDF>')


def test_looks_like_feed_rejects_html():
    assert not _looks_like_feed("<html><body>Not a feed</body></html>")


def test_looks_like_feed_rejects_xml_without_feed_tags():
    assert not _looks_like_feed('<?xml version="1.0"?><root><data>x</data></root>')


def test_looks_like_feed_rejects_empty():
    assert not _looks_like_feed("")


# ── _parse_homepage_links ──────────────────────────────────────────


def test_parse_homepage_rss_link():
    client = MagicMock(spec=httpx.Client)
    html = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'
    resp = MagicMock(status_code=200, text=html)
    client.get.return_value = resp

    result = _parse_homepage_links(client, "https://example.com")
    assert result == "https://example.com/feed.xml"


def test_parse_homepage_atom_link():
    client = MagicMock(spec=httpx.Client)
    html = '<html><head><link type="application/atom+xml" href="https://example.com/atom.xml"></head></html>'
    resp = MagicMock(status_code=200, text=html)
    client.get.return_value = resp

    result = _parse_homepage_links(client, "https://example.com")
    assert result == "https://example.com/atom.xml"


def test_parse_homepage_relative_href():
    client = MagicMock(spec=httpx.Client)
    html = '<link type="application/rss+xml" href="/rss/news.xml">'
    resp = MagicMock(status_code=200, text=html)
    client.get.return_value = resp

    result = _parse_homepage_links(client, "https://news.com")
    assert result == "https://news.com/rss/news.xml"


def test_parse_homepage_no_link():
    client = MagicMock(spec=httpx.Client)
    resp = MagicMock(status_code=200, text="<html><body>No feed links</body></html>")
    client.get.return_value = resp

    result = _parse_homepage_links(client, "https://example.com")
    assert result is None


def test_parse_homepage_non_200():
    client = MagicMock(spec=httpx.Client)
    resp = MagicMock(status_code=403, text="Forbidden")
    client.get.return_value = resp

    result = _parse_homepage_links(client, "https://example.com")
    assert result is None


def test_parse_homepage_http_error():
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = httpx.ConnectError("refused")

    result = _parse_homepage_links(client, "https://example.com")
    assert result is None


# ── _probe_common_paths ────────────────────────────────────────────


def test_probe_finds_rss_path():
    client = MagicMock(spec=httpx.Client)
    feed_xml = '<?xml version="1.0"?><rss><channel><item>x</item></channel></rss>'

    def mock_get(url):
        if url.endswith("/rss"):
            return MagicMock(status_code=200, text=feed_xml)
        return MagicMock(status_code=404, text="")

    client.get.side_effect = mock_get

    result = _probe_common_paths(client, "https://example.com")
    assert result == "https://example.com/rss"


def test_probe_skips_html_at_feed_path():
    """HTML returned at /feed should not be matched."""
    client = MagicMock(spec=httpx.Client)
    html = "<html><body>This is not a feed</body></html>"

    def mock_get(url):
        return MagicMock(status_code=200, text=html)

    client.get.side_effect = mock_get

    result = _probe_common_paths(client, "https://example.com")
    assert result is None


def test_probe_returns_none_all_404():
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = MagicMock(status_code=404, text="")

    result = _probe_common_paths(client, "https://example.com")
    assert result is None


def test_probe_handles_http_errors():
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = httpx.TimeoutException("timeout")

    result = _probe_common_paths(client, "https://example.com")
    assert result is None


# ── detect_rss_feed (integration) ──────────────────────────────────


def test_detect_rss_from_link_tag():
    """Detects RSS from homepage <link> tag."""
    html = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>'

    with patch("prism.agents.rss_detect.httpx.Client") as MockClient:
        client = MockClient.return_value
        resp = MagicMock(status_code=200, text=html)
        client.get.return_value = resp

        result = detect_rss_feed("example.com")
        assert result == "https://example.com/feed.xml"


def test_detect_rss_from_common_path():
    """Falls back to probing when homepage has no link tag."""
    feed_xml = '<?xml version="1.0"?><rss><channel><item>x</item></channel></rss>'

    with patch("prism.agents.rss_detect.httpx.Client") as MockClient:
        client = MockClient.return_value
        call_count = [0]

        def mock_get(url):
            call_count[0] += 1
            if url == "https://example.com":
                return MagicMock(status_code=200, text="<html>No links</html>")
            if url == "https://example.com/rss":
                return MagicMock(status_code=200, text=feed_xml)
            return MagicMock(status_code=404, text="")

        client.get.side_effect = mock_get

        result = detect_rss_feed("example.com")
        assert result == "https://example.com/rss"


def test_detect_rss_none_when_not_found():
    """Returns None when no RSS feed is found anywhere."""
    with patch("prism.agents.rss_detect.httpx.Client") as MockClient:
        client = MockClient.return_value
        client.get.return_value = MagicMock(status_code=404, text="")

        result = detect_rss_feed("nofeed.com")
        assert result is None


def test_detect_rss_handles_timeout():
    """Timeout during detection returns None, no crash."""
    with patch("prism.agents.rss_detect.httpx.Client") as MockClient:
        client = MockClient.return_value
        client.get.side_effect = httpx.TimeoutException("slow")

        result = detect_rss_feed("slow.com")
        assert result is None


def test_detect_rss_closes_client():
    """Client is always closed, even on failure."""
    with patch("prism.agents.rss_detect.httpx.Client") as MockClient:
        client = MockClient.return_value
        client.get.side_effect = httpx.ConnectError("refused")

        detect_rss_feed("down.com")
        client.close.assert_called_once()
