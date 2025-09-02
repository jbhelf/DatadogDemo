from bs4 import BeautifulSoup
import app.app as web  # your Flask app module is app/app.py


def test_anchor_href_matches_display(monkeypatch):
    # Force the bug OFF for this test
    monkeypatch.setattr(web, "BUG_REDIRECT", False)

    flask_app = web.app
    client = flask_app.test_client()

    # Act: create a short link
    resp = client.post("/shorten", data={"url": "https://example.com/page"}, follow_redirects=True)
    assert resp.status_code == 200

    soup = BeautifulSoup(resp.data, "html.parser")
    a = soup.select_one("a.short-link")
    assert a is not None, "short-link anchor not found"

    href = a.get("href", "")
    text = a.get_text(strip=True)

    # The rendered text is the full short URL; the href should match exactly
    assert href == text, f"href ({href}) != text ({text})"
