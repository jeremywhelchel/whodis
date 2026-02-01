# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- `/data.json` - JSON response
- `/data.png` - Dynamically generated PNG image
- `/data.jpeg` - Dynamically generated JPEG image

Key dependencies:
- `geocoder` - IP geolocation via ipinfo.io (rate limited to 50k requests/month, results cached with `lru_cache`)
- `ua-parser` - User-Agent string parsing
- `Pillow` - Dynamic image generation with RobotoMono-Medium.ttf font
- `google-cloud-logging` - Cloud logging when running in Cloud Run (detected via `K_SERVICE` env var)

In-memory stats (`STATS` dict) track device/OS/browser/country counts, displayed on index page. Stats reset on server restart.

Production uses gunicorn via the Dockerfile CMD.
