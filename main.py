#!/usr/bin/env python3

import collections
import datetime
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
import google.cloud.logging
import io
import json
import logging
import os
import pprint
from PIL import Image, ImageDraw, ImageFont
from ua_parser import user_agent_parser

app = Flask(__name__)
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = True


WIDTH = 800
HEIGHT = 640
ROBOTO = ImageFont.truetype("RobotoMono-Medium.ttf", 32)
# Maximum number of characters to fit in WIDTH
WIDTH_CHARS = int(800 / ROBOTO.getlength(" "))  # - 2


@app.route("/")
def index():
    return render_template(
        "index.html",
        data=get_request_text(),
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


@lru_cache(maxsize=100000)
def lookup_location(ip: str) -> dict:
    location = {}
    # This call is limited to 50k requests/month, or about 1.6k/day
    # https://ipinfo.io/developers#rate-limits
    g = geocoder.ip(ip)
    if g.ok:
        location = {"city": g.city, "country": g.country}
    return location


def request_data() -> dict:
    ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.remote_addr)
    location = lookup_location(ip)

    ua = user_agent_parser.Parse(request.headers["User-Agent"])

    d = {
        "ip": ip,
        "location": location,
        "device": ua["device"],
        "os": ua["os"],
        "browser": ua["user_agent"],
    }
    update_stats(d)
    return strip_dict(d)


def get_request_text() -> str:
    pp = pprint.PrettyPrinter(width=WIDTH_CHARS, sort_dicts=False)
    return pp.pformat(request_data())


@app.route("/data.json")
def as_json():
    return jsonify(request_data())


def make_image(fmt: str) -> io.BytesIO:
    msg = get_request_text()

    image = Image.new("RGB", (WIDTH, HEIGHT), color="blue")
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), msg, font=ROBOTO, fill=(255, 255, 0))

    image_data = io.BytesIO()
    image.save(image_data, format=fmt)
    image_data.seek(0)
    return image_data


@app.route("/data.png")
def as_png():
    return send_file(
        make_image("PNG"),
        mimetype="image/png",
    )


@app.route("/data.jpeg")
def as_jpeg():
    return send_file(
        make_image("JPEG"),
        mimetype="image/jpeg",
    )


def start_app():
    # If running in Google Cloud Run, use cloud logging
    if "K_SERVICE" in os.environ:
        # Setup Google Cloud logging
        # By default this captures all logs at INFO level and higher
        log_client = google.cloud.logging.Client()
        log_client.get_default_handler()
        log_client.setup_logging()
        logging.info("Using google cloud logging")
    else:
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Using standard logging")

    logging.info("Starting app")
    return app


if __name__ == "__main__":  # Run Flask dev-server directly
    logging.info("Running app.run()")
    start_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
