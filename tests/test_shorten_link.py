from bs4 import BeautifulSoup
from app.app import app as flask_app, BUG_REDIRECT


def test_anchor_href_matches_display():
    client = flask_app.test_client()

    # Act: create a short link
    resp = client.post("/shorten", data={"url": "https://example.com/page"}, follow_redirects=True)
    assert resp.status_code == 200

    soup = BeautifulSoup(resp.data, "html.parser")
    a = soup.select_one("a.short-link")
    assert a is not None, "short-link anchor not found"

    href = a.get("href", "")
    text = a.get_text(strip=True)

    if BUG_REDIRECT:
        # When the bug flag is ON, the href should point 
        # to Datadog and not equal the displayed short URL
        assert "datadog.com" in href, f"expected datadog.com in href, got {href}"
        assert href != text, "href should not match displayed short URL when BUG_REDIRECT is True"
    else:
        # When the bug flag is OFF, href must equal the displayed short URL
        assert href == text, f"href ({href}) != text ({text})"
