#!/usr/bin/env python3

import collections
import datetime
import re
from flask import (
    Flask,
    jsonify,
    Response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from functools import lru_cache
import geocoder
import io
import json
import logging
import os
import pprint
import sys
from PIL import Image, ImageDraw, ImageFont
from ua_parser import user_agent_parser

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True


WIDTH = 800
HEIGHT = 640
ROBOTO = ImageFont.truetype("RobotoMono-Medium.ttf", 32)
ROBOTO_SMALL = ImageFont.truetype("RobotoMono-Medium.ttf", 20)
# Maximum number of characters to fit in WIDTH
WIDTH_CHARS = int(800 / ROBOTO.getlength(" "))  # - 2

# Raw request headers that reveal something the parsed UA doesn't,
# or that users are surprised to learn they send.
INTERESTING_HEADERS = [
    "Accept-Language",
    "Referer",
    "Sec-CH-UA",
    "Sec-CH-UA-Mobile",
    "Sec-CH-UA-Platform",
    "Sec-CH-UA-Full-Version-List",
    "Sec-Fetch-Dest",
    "Sec-Fetch-Mode",
    "Sec-Fetch-Site",
    "Sec-Fetch-User",
    "Upgrade-Insecure-Requests",
    "DNT",
    "Priority",
]


@app.route("/")
def index():
    return render_template(
        "index.html",
        data=get_full_text(),
        top_lists=get_top_stats(),
    )


def strip_dict(d: dict) -> dict:
    """Remove None values from dict, recursively."""
    clean = {}
    for k, v in d.items():
        if isinstance(v, dict):
            nested = strip_dict(v)
            if nested:
                clean[k] = nested
        elif v is not None:
            clean[k] = v
    return clean


STATS = {
    "device": collections.Counter(),
    "os": collections.Counter(),
    "browser": collections.Counter(),
    "country": collections.Counter(),
}


def update_stats(d: dict):
    global STATS

    if "family" in d["device"]:
        device = d["device"]["family"]
        STATS["device"][device] += 1

    if "family" in d["os"]:
        os = d["os"]["family"]
        STATS["os"][os] += 1

    if "family" in d["browser"]:
        os = d["browser"]["family"]
        STATS["browser"][os] += 1

    if "country" in d["location"]:
        country = d["location"]["country"]
        STATS["country"][country] += 1


def get_top_stats() -> dict:
    """Generate the top values for each stats bucket."""
    top_lists = {}
    for name, stats in STATS.items():
        top_lists[name] = stats.most_common(5)
    return top_lists


# Only successful lookups are cached; failures (bad IPs, rate-limit
# responses) are retried on the next request so a permanent negative
# result never occupies a cache slot or masks a transient error.
# Cap the cache to keep memory bounded; clearing it entirely is fine
# since it is purely an optimization.
_location_cache: dict = {}


def lookup_location(ip: str) -> dict:
    if ip in _location_cache:
        return _location_cache[ip]

    # This call is limited to 50k requests/month, or about 1.6k/day
    # https://ipinfo.io/developers#rate-limits
    g = geocoder.ip(ip)
    if not g.ok:
        return {}

    location = {"city": g.city, "country": g.country}
    if len(_location_cache) >= 100_000:
        _location_cache.clear()
    _location_cache[ip] = location
    return location


def request_data() -> dict:
    # X-Forwarded-For is a comma-separated chain. Earlier entries are
    # client-controlled; the rightmost is appended by the nearest trusted
    # proxy, so it is the only entry worth trusting.
    ip = request.environ.get(
        "HTTP_X_FORWARDED_FOR", request.remote_addr
    ).split(",")[-1].strip()
    location = lookup_location(ip)

    ua = user_agent_parser.Parse(request.headers.get("User-Agent", ""))

    d = {
        "ip": ip,
        "location": location,
        "device": ua["device"],
        "os": ua["os"],
        "browser": ua["user_agent"],
    }
    d["headers"] = {
        name: value
        for name in INTERESTING_HEADERS
        if (value := request.headers.get(name)) is not None
    }
    update_stats(d)
    return strip_dict(d)


def request_summary() -> dict:
    d = request_data()
    return {k: d[k] for k in ("ip", "location", "device", "os", "browser") if k in d}


def get_summary_text() -> str:
    pp = pprint.PrettyPrinter(width=WIDTH_CHARS, sort_dicts=False)
    return pp.pformat(request_summary())


def get_full_text() -> str:
    pp = pprint.PrettyPrinter(width=WIDTH_CHARS, sort_dicts=False)
    return pp.pformat(request_data())


@app.route("/data.json")
def as_json():
    return jsonify(request_data())


def make_image(fmt: str, full: bool = False) -> io.BytesIO:
    if full:
        msg = get_full_text()
        # Dynamic canvas sized to fit every line at the smaller font.
        font = ROBOTO_SMALL
        line_height = font.size + 6
        lines = msg.splitlines() or [""]
        height = 16 + len(lines) * line_height
    else:
        msg = get_summary_text()
        font = ROBOTO
        height = HEIGHT

    image = Image.new("RGB", (WIDTH, height), color="blue")
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), msg, font=font, fill=(255, 255, 0))

    image_data = io.BytesIO()
    image.save(image_data, format=fmt)
    image_data.seek(0)
    return image_data


@app.route("/data.png")
def as_png():
    return send_file(make_image("PNG"), mimetype="image/png")


@app.route("/data.jpeg")
def as_jpeg():
    return send_file(make_image("JPEG"), mimetype="image/jpeg")


@app.route("/data.full.png")
def as_full_png():
    return send_file(make_image("PNG", full=True), mimetype="image/png")


@app.route("/data.full.jpeg")
def as_full_jpeg():
    return send_file(make_image("JPEG", full=True), mimetype="image/jpeg")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class JsonFormatter(logging.Formatter):
    """Emit each log record as a JSON line on stdout.

    Cloud Run parses stdout JSON blobs as structured logs and maps the
    standard "severity" field onto Cloud Logging severities. ANSI color
    codes are stripped so aggregators never see escape sequences.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": _ANSI_RE.sub("", record.getMessage()),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def start_app():
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.info("Starting app")
    return app


if __name__ == "__main__":  # Run Flask dev-server directly
    logging.info("Running app.run()")
    start_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
