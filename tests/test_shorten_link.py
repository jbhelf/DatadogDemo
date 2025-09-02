from bs4 import BeautifulSoup
from app.app import app as flask_app


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

    assert href == text, f"href ({href}) != text ({text})"
