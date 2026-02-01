A simple webserver illustrating information leakage during web requests.

Dynamically generates an image containing request info:
- IP and derived location info
- Device, operating system, browser

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
