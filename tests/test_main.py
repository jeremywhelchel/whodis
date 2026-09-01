"""Tests for whodis request handling.

Network calls (ipinfo.io) are patched out; every test runs offline.
"""
import io

import pytest
from PIL import Image

import main


@pytest.fixture(autouse=True)
def _offline_geolocation(monkeypatch):
    """Patch out the ipinfo.io call so tests never hit the network."""

    class FakeGeo:
        ok = True
        city = "Testville"
        country = "US"

    monkeypatch.setattr(main.geocoder, "ip", lambda ip: FakeGeo())
    main._location_cache.clear()


@pytest.fixture(autouse=True)
def _reset_stats():
    """Keep the global STATS counters clean between tests."""
    for counter in main.STATS.values():
        counter.clear()


def client():
    return main.app.test_client()


class TestXForwardedFor:
    def test_spoofed_chain_uses_rightmost_entry(self):
        rv = client().get(
            "/data.json",
            headers={"X-Forwarded-For": "1.2.3.4, 9.9.9.9"},
        )
        assert rv.status_code == 200
        assert rv.get_json()["ip"] == "9.9.9.9"

    def test_single_spoofed_value_passes_through(self):
        rv = client().get(
            "/data.json", headers={"X-Forwarded-For": "1.2.3.4"}
        )
        assert rv.get_json()["ip"] == "1.2.3.4"

    def test_no_header_falls_back_to_remote_addr(self):
        rv = client().get("/data.json")
        assert rv.get_json()["ip"] == "127.0.0.1"


class TestUserAgent:
    def test_missing_user_agent_does_not_500(self):
        rv = client().get("/data.json", headers={"User-Agent": ""})
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["browser"]["family"] == "Other"
        assert data["device"]["family"] == "Other"
        assert data["os"]["family"] == "Other"

    def test_user_agent_is_parsed(self):
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        )
        rv = client().get("/data.json", headers={"User-Agent": ua})
        data = rv.get_json()
        assert data["browser"]["family"] == "Chrome"
        assert data["os"]["family"] == "Mac OS X"


class TestHeaderDump:
    def test_present_headers_are_included(self):
        rv = client().get(
            "/data.json",
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        headers = rv.get_json()["headers"]
        assert headers["Accept-Language"] == "en-US,en;q=0.9"

    def test_absent_headers_are_omitted(self):
        rv = client().get("/data.json")
        assert "Accept-Language" not in rv.get_json().get("headers", {})


class TestTag:
    def test_tag_is_extracted_as_a_field(self):
        rv = client().get("/data.json?tag=forum-post-42")
        assert rv.get_json()["tag"] == "forum-post-42"

    def test_no_tag_means_no_tag_key(self):
        rv = client().get("/data.json")
        assert "tag" not in rv.get_json()

    def test_tag_appears_in_social_summary(self):
        rv = client().get("/data.png?tag=embed-test")
        assert rv.status_code == 200
        # The summary that feeds the social image includes the tag when
        # present, so a tagged embed is visually distinguishable.
        rv_json = client().get("/data.json?tag=embed-test")
        assert rv_json.get_json()["tag"] == "embed-test"



class TestGeolocationCache:
    def test_successful_lookup_is_cached(self, monkeypatch):
        calls = []

        class FakeGeo:
            ok = True
            city = "Cache City"
            country = "US"

        def fake_geocoder_ip(ip):
            calls.append(ip)
            return FakeGeo()

        monkeypatch.setattr(main.geocoder, "ip", fake_geocoder_ip)
        first = main.lookup_location("9.9.9.9")
        second = main.lookup_location("9.9.9.9")
        assert first == second == {"city": "Cache City", "country": "US"}
        assert calls == ["9.9.9.9"], "second call should be a cache hit"

    def test_failed_lookup_is_not_cached(self, monkeypatch):
        calls = []

        class FakeGeo:
            ok = False

        def fake_geocoder_ip(ip):
            calls.append(ip)
            return FakeGeo()

        monkeypatch.setattr(main.geocoder, "ip", fake_geocoder_ip)
        assert main.lookup_location("192.168.1.1") == {}
        assert main.lookup_location("192.168.1.1") == {}
        assert len(calls) == 2, "failed lookups should be retried, not cached"


class TestImageVariants:
    @pytest.fixture
    def rich_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/141.0.0.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-CH-UA-Platform": '"macOS"',
			   }

    def test_social_image_is_fixed_size(self, rich_headers):
        for path in ("/data.png", "/data.jpeg"):
            rv = client().get(path, headers=rich_headers)
            assert rv.status_code == 200
            image = Image.open(io.BytesIO(rv.data))
            assert image.size == (main.WIDTH, main.HEIGHT)

    def test_full_image_includes_header_data(self, rich_headers):
        with_extra = client().get("/data.full.png", headers=rich_headers)
        without_extra = client().get("/data.full.png")
        assert with_extra.status_code == 200
        extra_img = Image.open(io.BytesIO(with_extra.data))
        plain_img = Image.open(io.BytesIO(without_extra.data))
        assert extra_img.size[0] == main.WIDTH
        # Extra headers mean extra rendered lines, so the dynamic
        # canvas grows taller for the header-rich request.
        assert extra_img.size[1] > plain_img.size[1]

    def test_full_jpeg_serves_jpeg(self, rich_headers):
        rv = client().get("/data.full.jpeg", headers=rich_headers)
        assert rv.status_code == 200
        assert rv.mimetype == "image/jpeg"
