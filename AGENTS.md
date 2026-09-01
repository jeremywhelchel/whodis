# AGENTS.md

Guidance for AI coding agents working in this repository, regardless of harness.

## Project Overview


whodis is a Flask web application that demonstrates information leakage during web requests. It displays visitor information (IP, location, device, OS, browser) extracted from HTTP headers, available as HTML, JSON, PNG, or JPEG.

Live at: https://whodis.fyi

## Commands

**Local development:**
```bash
uv sync
uv run python main.py
# Visit http://localhost:8080/
```

**With Docker:**
```bash
docker build -t whodis .
docker run -e PORT=80 -p 12345:80 whodis
# Visit http://localhost:12345/
```

**Deploy to Google Cloud Run:**
```bash
./build_and_deploy.sh
```

## Architecture

Single-file Flask app (`main.py`) with these endpoints:
- `/` - HTML page with request info and stats
- `/data.json` - JSON response (includes `?tag=...` when present)
- `/data.png` - Social PNG image (fixed size, summary only)
- `/data.jpeg` - Social JPEG image (fixed size, summary only)
- `/data.full.png` - Full PNG image (all headers, auto-sized canvas)
- `/data.full.jpeg` - Full JPEG image (all headers, auto-sized canvas)

Key dependencies:
- `geocoder` - IP geolocation via ipinfo.io (rate limited to 50k requests/month, successful results cached)
- `ua-parser` - User-Agent string parsing
- `Pillow` - Dynamic image generation with RobotoMono-Medium.ttf font

In-memory stats (`STATS` dict) track device/OS/browser/country counts, displayed on index page. Stats reset on server restart.

Logging is JSON lines on stdout (parsed as structured logs by Cloud Run). The service computes request data per request and retains no per-request storage.

Production uses gunicorn via the Dockerfile CMD.
