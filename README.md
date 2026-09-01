A simple webserver illustrating information leakage during web requests.

Dynamically generates an image containing request info:
- IP and derived location info
- Device, operating system, browser

Also available as HTML and JSON, with a full variant that includes
interesting request headers (client hints, fetch metadata, etc.):
- `/` — HTML page
- `/data.json` — JSON
- `/data.png`, `/data.jpeg` — social image (fixed size, summary)
- `/data.full.png`, `/data.full.jpeg` — full image (all headers, auto-sized)

An optional `?tag=...` query parameter labels the request and is echoed
back to the requester like every other field.

Run locally via:

```bash
uv sync
uv run python main.py
# Visit http://localhost:8080/
```

Or with Docker:

```bash
docker build -t whodis .
docker run -e PORT=80 -p 12345:80 whodis
# Visit http://localhost:12345/
```

Tests (offline, no network):

```bash
uv run pytest
```

Logging: JSON lines on stdout (Cloud Run parses these as structured logs).
The service computes request data per request and retains only aggregate
in-memory stats; there is no per-request storage.
