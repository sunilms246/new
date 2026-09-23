"""
MDN HTTP Status Dataset Builder
===============================

Expands data/mdn_http_status.json to full HTTP status code coverage.

Source: github.com/mdn/content (files/en-us/web/http/reference/status/<code>/index.md)
Attribution: MDN Web Docs by Mozilla contributors, CC-BY-SA 2.5.

The real MDN prose (title, summary, description) is downloaded and parsed from the
repo, while QA-specific fields (causes, remediation, keywords, recommended_steps)
are curated below for tester-facing quality. Codes already present in the dataset
are preserved verbatim.

Usage:
    python scripts/build_dataset.py
"""

import json
import os
import re
import sys
import urllib.request

BASE_URL = "https://raw.githubusercontent.com/mdn/content/main"
STATUS_DIR = "files/en-us/web/http/reference/status"
DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mdn_http_status.json")

# Codes documented in mdn/content (files/en-us/web/http/reference/status), excluding index.md
STATUS_CODES = [
    100, 101, 102, 103,
    200, 201, 202, 203, 204, 205, 206, 207, 208, 226,
    300, 301, 302, 303, 304, 307, 308,
    400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416,
    417, 418, 421, 422, 423, 424, 425, 426, 428, 429, 431, 451,
    500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511,
]

# Categorized QA content for codes NOT already present in the existing dataset.
# key: causes (list), remediation, keywords (list)
CURATED = {
    100: {
        "causes": ["Client sent Expect: 100-continue header while uploading a request body", "Server configuration rejects large body uploads before reading them", "Reverse proxy strips or mishandles the Expect header"],
        "remediation": "Verify the Expect: 100-continue handshake is honored for large uploads; if the server should always read bodies, disable the Expect header in the proxy.",
        "keywords": ["100", "continue", "expect header"],
    },
    101: {
        "causes": ["WebSocket or HTTP/2 upgrade handshake being negotiated", "Server configured to upgrade protocols (e.g. HTTP/1.1 to HTTP/2)", "Testing tools that treat a successful upgrade as an error"],
        "remediation": "This is a normal switching-protocols response; QA should treat it as success when protocol upgrade is expected.",
        "keywords": ["101", "switching protocols", "websocket upgrade"],
    },
    102: {
        "causes": ["Long-running WebDAV or batch processing where server sends interim progress", "Server takes longer than the client timeout to produce a final response"],
        "remediation": "Ensure long jobs stream progress and eventually return a final status; tune client timeouts for interim responses.",
        "keywords": ["102", "processing", "webdav processing"],
    },
    103: {
        "causes": ["Server sending early response headers to hint preload resources", "CDN/proxy not handling early hints, dropping Link headers"],
        "remediation": "Confirm the Link preload hints reach the browser and that proxies forward 103 responses without erroring.",
        "keywords": ["103", "early hints", "preload"],
    },
    200: {
        "causes": ["Request completed successfully (baseline/happy-path)", "QA regression check expecting 200 but the flow actually fails elsewhere", "Caching layers serving stale success responses"],
        "remediation": "Verify response body matches expected data; if cached, check Cache-Control headers rather than assuming a live call.",
        "keywords": ["200", "ok", "success response", "loads fine"],
    },
    201: {
        "causes": ["Resource created successfully (POST/PUT happy path)", "Expecting 201 but receiving 200 because API returns no Location header", "Idempotency issues on retry creating duplicate resources"],
        "remediation": "Ensure creation endpoints return 201 with a Location header; verify retries do not create duplicates.",
        "keywords": ["201", "created", "resource created"],
    },
    202: {
        "causes": ["Asynchronous job accepted but not yet completed", "Background task queue (workers) has not processed the request", "Long-running operation returns early without confirmation"],
        "remediation": "Poll the job status endpoint until completion; log the async job ID returned in the response.",
        "keywords": ["202", "accepted", "queued job", "async request"],
    },
    203: {
        "causes": ["Proxy/CDN transforms the response (e.g. modifies headers or body)", "Meta-information differs from origin server"],
        "remediation": "Compare origin vs transformed response headers when debugging content differences through CDNs.",
        "keywords": ["203", "non-authoritative", "transformed response"],
    },
    204: {
        "causes": ["Success with no body (DELETE or silent update)", "Front-end expects a body but gets an empty response", "Redirect target returns an empty success"],
        "remediation": "Client code should not parse a body on 204; server should confirm nothing needs returning.",
        "keywords": ["204", "no content", "empty response"],
    },
    205: {
        "causes": ["Form submit returns 205 telling the client to reset the document view", "Browser not handling reset, leaving stale form data"],
        "remediation": "Ensure the form view resets after a 205; QA should verify the form is cleared on submit.",
        "keywords": ["205", "reset content", "form reset"],
    },
    206: {
        "causes": ["Partial content served for a Range request (video/resume downloads)", "Server ignoring Range and returning full 200 instead", "Incorrect Content-Range header causing download corruption"],
        "remediation": "Validate Content-Range and Content-Length on partial downloads; resume and seek must reproduce the correct byte range.",
        "keywords": ["206", "partial content", "range request", "download resume", "video seek", "streaming range"],
    },
    207: {
        "causes": ["WebDAV multi-status response with per-resource results", "Some sub-resources failed while others succeeded", "Client parses only the first sub-status"],
        "remediation": "Parse all entries inside the multi-status body; report success/failure per sub-resource, not globally.",
        "keywords": ["207", "multi status", "webdav multi"],
    },
    208: {
        "causes": ["WebDAV PROPFIND listing already-reported member resources", "Duplicated entries from nested report"],
        "remediation": "For 207/208 responses, deduplicate listed resources on the client side.",
        "keywords": ["208", "already reported", "webdav report"],
    },
    226: {
        "causes": ["Server applied delta encoding to the response body", "CDN/proxy does not support delta encoding, falling back to full content"],
        "remediation": "Confirm only the delta is returned and cache-control handles stale deltas correctly.",
        "keywords": ["226", "im used", "delta encoding"],
    },
    300: {
        "causes": ["Multiple representations available (content negotiation)", "Server returns a menu of choices that client did not auto-select"],
        "remediation": "Choose the correct representation manually or via Accept headers; avoid forcing users through a choice page.",
        "keywords": ["300", "multiple choices"],
    },
    301: {
        "causes": ["Resource moved permanently to a new URL", "Missing trailing-slash redirect or domain migration left behind", "Old bookmarks hitting obsolete endpoints without a redirect"],
        "remediation": "Update internal links and add 301 redirects from old to new URLs; invalidate caches that stored the old Location.",
        "keywords": ["301", "moved permanently", "redirect", "redirect loop", "url moved"],
    },
    302: {
        "causes": ["Temporary redirect after POST (PRG pattern)", "OAuth login flows redirecting to/from identity provider", "Redirect target returning an error that masks the real defect"],
        "remediation": "Follow redirects during testing and verify the final landing page; keep method semantics for PRG flows.",
        "keywords": ["302", "found", "temporary redirect", "login redirect"],
    },
    303: {
        "causes": ["POST results redirecting to a GET resource", "Client not following the See Other redirect"],
        "remediation": "Confirm the client follows 303 to the location and refreshes the result view.",
        "keywords": ["303", "see other", "post redirect get"],
    },
    304: {
        "causes": ["Cached copy is still valid (If-None-Match/If-Modified-Since)", "ETag/Last-Modified validation mismatch causing stale caches", "QA expecting fresh content but getting cached 304"],
        "remediation": "Verify cache validation headers; when content changes, ensure ETag/Last-Modified updates so caches revalidate.",
        "keywords": ["304", "not modified", "cache hit"],
    },
    307: {
        "causes": ["Temporary redirect preserving method and body", "Cross-origin redirects failing CORS/credentials", "Infinite redirect chain between two endpoints"],
        "remediation": "Check redirect chains in DevTools; preserve method/body semantics and fix loops.",
        "keywords": ["307", "redirect", "temporary redirect", "method redirect"],
    },
    308: {
        "causes": ["Permanent redirect preserving method and body (PUT/POST)", "API clients caching the new URL permanently even after revert"],
        "remediation": "Update clients to the permanent URL; avoid 308 during transient maintenance windows.",
        "keywords": ["308", "permanent redirect", "redirect"],
    },
    402: {
        "causes": ["Payment required feature not yet implemented", "Billing/payment gateway returning placeholder 402", "Paywall blocks access without subscription"],
        "remediation": "Implement or clearly surface payment-gated behavior; check the gateway integration for billing defects.",
        "keywords": ["402", "payment required", "paywall"],
    },
    405: {
        "causes": ["Wrong HTTP method used against endpoint (e.g. GET vs POST)", "Method not routed on the server (missing @app.route for POST)", "Form/JavaScript calling the wrong verb"],
        "remediation": "Match front-end calls to the allowed methods; verify each endpoint's allowed methods in the Allow header.",
        "keywords": ["405", "method not allowed", "get not allowed", "post not allowed", "delete not allowed", "wrong http method"],
    },
    406: {
        "causes": ["Accept header requests a representation the server cannot produce", "Wrong Accept header (e.g. application/xml requested, JSON only available)", "Content negotiation misconfiguration"],
        "remediation": "Align Accept headers with available media types or support the requested format.",
        "keywords": ["406", "not acceptable", "content negotiation", "accept header"],
    },
    407: {
        "causes": ["Proxy requires authentication and client did not provide proxy credentials", "Corporate proxy blocking automated tests", "Stale proxy credentials"],
        "remediation": "Provide correct proxy credentials/configuration in the test environment and header setup.",
        "keywords": ["407", "proxy authentication", "proxy auth", "proxy credentials"],
    },
    410: {
        "causes": ["Resource intentionally deleted with no redirect", "API version removed an endpoint that clients still call", "Deprecated content link never updated"],
        "remediation": "Return 410 loudly and update or remove stale references/links pointing to deleted resources.",
        "keywords": ["410", "gone", "removed resource", "deleted resource"],
    },
    411: {
        "causes": ["Missing or invalid Content-Length header", "Server requires Content-Length but request is chunked", "Proxy stripping Content-Length"],
        "remediation": "Ensure the client sends a correct Content-Length or switch to chunked encoding consistently.",
        "keywords": ["411", "length required", "content-length missing"],
    },
    412: {
        "causes": ["If-Match/If-None-Match precondition failed due to ETag mismatch", "Optimistic locking conflict on stale client data", "Conditional header from retry logic not matching"],
        "remediation": "Refresh the resource state in the client before retrying; validate ETag handling server-side.",
        "keywords": ["412", "precondition failed", "etag mismatch", "if-match failed", "optimistic locking"],
    },
    413: {
        "causes": ["Uploaded file/request body exceeds server limit", "Base64 or multipart encoding inflating payload size", "Misconfigured proxy body-size limit"],
        "remediation": "Raise or align body size limits across app/proxy/load balancer; add client-side file-size validation and clear error messaging.",
        "keywords": ["413", "payload too large", "request too large", "file too large", "upload too big", "413 too large"],
    },
    414: {
        "causes": ["Huge query string or URL exceeding server limit", "Application appending nonce/trace data to URLs", "Proxy limits on request line length"],
        "remediation": "Move large inputs into POST bodies; truncate/search long URLs or raise server URI limits.",
        "keywords": ["414", "uri too long", "url too long"],
    },
    415: {
        "causes": ["Wrong Content-Type header (e.g. text/plain instead of application/json)", "Uploading unsupported file type/extension", "Server only accepts certain media types"],
        "remediation": "Set the correct Content-Type on requests and match server-supported formats; validate upload MIME types client-side.",
        "keywords": ["415", "unsupported media type", "wrong content type", "invalid file format", "content type mismatch"],
    },
    416: {
        "causes": ["Range request asks for a range outside the resource size", "Wrong Content-Range math in video/resume features", "Server returns full 200 instead of 416 for bad ranges"],
        "remediation": "Validate the requested byte range and reply with Content-Range; fix client range calculation.",
        "keywords": ["416", "range not satisfiable", "invalid range", "bad range request"],
    },
    417: {
        "causes": ["Expect: 100-continue expectation cannot be filled by server", "Proxies mishandling the Expect header"],
        "remediation": "Update or remove the Expect header if the server can't meet it; fix proxy header forwarding.",
        "keywords": ["417", "expectation failed", "expect header failed"],
    },
    418: {
        "causes": ["Aprils-fool easter-egg endpoint intentionally returns 418", "Client handling of non-standard status codes as errors"],
        "remediation": "Do not rely on 418 in production contracts; treat as a non-standard informational response.",
        "keywords": ["418", "teapot", "im a teapot"],
    },
    421: {
        "causes": ["Request sent to server that cannot produce a response for the target (HTTP/2)", "Sticky-session load balancer routing a request to the wrong backend", "Virtual host not configured on that node"],
        "remediation": "Ensure connection pooling and routing send requests to nodes able to answer the Host/authority.",
        "keywords": ["421", "misdirected request", "wrong backend", "connection reuse"],
    },
    422: {
        "causes": ["Request is well-formed but semantically invalid (business rule violation)", "Duplicate unique fields, invalid enum values, or inconsistent data", "Validation errors beyond format, e.g. logic/state violations"],
        "remediation": "Return detailed field-level errors; align front-end validation with backend business rules.",
        "keywords": ["422", "unprocessable", "unprocessable entity", "semantic error", "business validation", "422 validation"],
    },
    423: {
        "causes": ["Resource locked (WebDAV or application-level lock)", "Concurrent edit/save blocked by another session"],
        "remediation": "Surface the lock owner and allow force-unlock where appropriate; release locks on session end.",
        "keywords": ["423", "locked", "resource locked", "file locked"],
    },
    424: {
        "causes": ["Dependent request failed before this one could proceed", "Previous step in a workflow/transaction failed", "WebDAV dependency chain broken"],
        "remediation": "Check and fix the upstream dependency before retrying; return clear context about which dependency failed.",
        "keywords": ["424", "failed dependency", "dependency failed"],
    },
    425: {
        "causes": ["Client replayed a request too early before the server is ready", "HTTP/2 replay protection trigger"],
        "remediation": "Add replay protection/idempotency keys; retry the request after the server signals readiness.",
        "keywords": ["425", "too early", "replay protection"],
    },
    426: {
        "causes": ["Server requires an upgraded protocol (e.g. HTTP/2, WebSocket)", "Client using old protocol version that server no longer accepts"],
        "remediation": "Negotiate the required protocol upgrade before sending the actual request.",
        "keywords": ["426", "upgrade required", "protocol upgrade", "http2 required"],
    },
    428: {
        "causes": ["Missing conditional request header (If-Match/If-Unmodified-Since)", "Optimistic locking requires preconditions not sent by client"],
        "remediation": "Send the required precondition headers in client requests to protect against races.",
        "keywords": ["428", "precondition required", "conditional header missing"],
    },
    431: {
        "causes": ["Request header fields exceed server limits", "Too many/sizeable cookies or custom headers (token bloat)", "Proxy stripping and re-adding oversized headers"],
        "remediation": "Trim cookie/header size, encrypt data server-side instead of embedding in headers, and raise header limits consistently.",
        "keywords": ["431", "header too large", "request header too long", "cookie too large", "headers too big"],
    },
    451: {
        "causes": ["Content blocked for legal/censorship reasons", "Geo-blocking or regulatory filtering middleware", "Country-specific content unavailability"],
        "remediation": "Communicate the legal block clearly in the UI and return the correct status to consumers.",
        "keywords": ["451", "unavailable for legal reasons", "legal block", "content blocked"],
    },
    501: {
        "causes": ["Server does not implement the requested method/feature", "API endpoint registered but not yet implemented", "Missing server-side handler for a new HTTP method"],
        "remediation": "Implement the handler or remove the capability that exposes an unimplemented endpoint.",
        "keywords": ["501", "not implemented", "unsupported method"],
    },
    505: {
        "causes": ["Client speaks an unsupported HTTP version (e.g. HTTP/0.9, HTTP/1.0 vs HTTP/2)", "Protocol negotiation mismatch behind proxies"],
        "remediation": "Align client and server HTTP versions; upgrade the client library or configure protocol downgrade rules.",
        "keywords": ["505", "http version not supported", "version not supported"],
    },
    506: {
        "causes": ["Server configuration causes content negotiation to reference itself", "Conflicting variants configured for the same resource"],
        "remediation": "Review server content-negotiation configuration and remove circular variant references.",
        "keywords": ["506", "variant also negotiates", "negotiation loop"],
    },
    507: {
        "causes": ["Server/backing store out of disk or in-memory capacity", "Uploads or file operations fail when storage is full", "WebDAV storage quota exceeded"],
        "remediation": "Free storage or scale the storage backend; add capacity alerting and graceful user feedback.",
        "keywords": ["507", "insufficient storage", "disk full", "storage full", "out of space"],
    },
    508: {
        "causes": ["Infinite redirect loop detected (A -> B -> A)", "Recursive include/template rendering detected by server", "Misconfigured rewrite rules causing a loop"],
        "remediation": "Remove the circular reference; trace the redirect chain via DevTools and fix the looping rewrite/directive.",
        "keywords": ["508", "loop detected", "infinite loop", "redirect loop"],
    },
    510: {
        "causes": ["Client did not declare the extensions the server requires", "Server policy needs mandatory extension negotiation"],
        "remediation": "Declare the required HTTP extensions or adjust server settings requiring them.",
        "keywords": ["510", "not extended"],
    },
    511: {
        "causes": ["Captive-portal/guest WiFi requires network sign-in before loading pages", "Corporate network authentication portal intercepting requests", "Credentials required but no browser prompt shown in app/webview"],
        "remediation": "Direct clients to the authentication portal; exclude the captive portal IP from app network checks.",
        "keywords": ["511", "network authentication", "captive portal", "wifi login"],
    },
}

# Generic test-step template used for newly added status codes.
GENERIC_STEPS = [
    "Open the application in a web browser or API client at the affected endpoint",
    "Reproduce the scenario corresponding to the defect (e.g. perform the exact failing action)",
    "Inspect the DevTools Network tab or server logs and capture the exact request/response headers",
]


def fetch_page(code):
    url = f"{BASE_URL}/{STATUS_DIR}/{code}/index.md"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"  [skip] failed to fetch {code}: {e}")
        return None


def clean_markdown(text):
    text = re.sub(r"\{\{[A-Za-z]+\(\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*\)\}\}", r"\1 (\2)", text)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("**", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_page_code(raw, code):
    """Extract title/summary/description from raw MDN markdown."""
    lines = raw.splitlines()
    body_start = None
    for i, line in enumerate(lines):
        if line.strip() == "---" and i > 0:
            body_start = i + 1
            break

    paragraphs = []
    for line in lines[body_start:]:
        if line.startswith("#"):
            break
        if line.strip():
            paragraphs.append(line.strip())

    summary = clean_markdown(paragraphs[0]) if paragraphs else f"HTTP {code} status."

    desc_body = paragraphs[1:5] if len(paragraphs) > 1 else []
    description = clean_markdown(" ".join(desc_body)) if desc_body else summary
    if len(description) > 1400:
        description = description[:1397].rstrip() + "..."

    return summary, description


def category_for(code):
    if 100 <= code <= 199:
        return "Informational"
    if 200 <= code <= 299:
        return "Successful"
    if 300 <= code <= 399:
        return "Redirection"
    if 400 <= code <= 499:
        return "Client Error"
    return "Server Error"


def main():
    if not os.path.exists(DATA_PATH):
        print("Existing dataset not found; starting from scratch.")
        existing = {}
    else:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            existing = {int(x["code"]): x for x in json.load(f)}
    print(f"Existing entry codes ({len(existing)}): {sorted(existing)}")

    new_entries = []
    for code in STATUS_CODES:
        if code in existing:
            continue

        raw = fetch_page(code)
        if raw is None:
            print(f"  [warn] no MDN content for {code}; writing entry from curated data only")
            summary = f"HTTP {code} status."
            description = summary
        else:
            summary, description = parse_page_code(raw, code)

        curated = CURATED.get(code, {})
        name_title = None
        if raw:
            m = re.search(r"^title:\s*(.+)$", raw, re.MULTILINE)
            name_title = m.group(1).strip() if m else None
        if not name_title:
            name_title = f"{code} {summary.split(' ', 1)[-1][:40]}" if summary.startswith("HTTP ") else f"{code} Status"

        entry = {
            "code": code,
            "name": name_title,
            "category": category_for(code),
            "summary": summary,
            "description": description,
            "causes": curated.get("causes", [f"Behavior associated with HTTP {code} observed in the application."]),
            "recommended_steps": [s for s in GENERIC_STEPS],
            "remediation": curated.get("remediation", "Inspect application logs and network trace for the failing request."),
            "mdn_url": f"https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/{code}",
            "keywords": curated.get("keywords", [str(code)]),
        }
        new_entries.append(entry)
        print(f"  + added {code} ({name_title})")

    final = list(existing.values()) + new_entries
    final.sort(key=lambda x: x["code"])

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\nDone. Total entries: {len(final)} (added {len(new_entries)}), written to {DATA_PATH}")


if __name__ == "__main__":
    sys.exit(main())