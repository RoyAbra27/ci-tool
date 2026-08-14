"""HTTP layer: one entry point, bounded retries that honor Retry-After."""

import time

import httpx

TIMEOUT = 10.0
MAX_ATTEMPTS = 3
RETRYABLE = {429, 500, 502, 503, 504}
UA = "ci-tool/0.1 (competitive-intelligence pipeline)"


def _retry_delay(resp: httpx.Response | None, attempt: int) -> float:
    if resp is not None:
        ra = resp.headers.get("retry-after", "")
        if ra.isdigit():
            return min(float(ra), 60.0)
    return float(2**attempt)


def get_text(url: str, *, params: dict | None = None) -> str:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = None
        try:
            resp = httpx.get(
                url, params=params, timeout=TIMEOUT,
                headers={"User-Agent": UA}, follow_redirects=True,
            )
            if resp.status_code < 400:
                return resp.text
            if resp.status_code not in RETRYABLE:
                resp.raise_for_status()
            last_error = httpx.HTTPStatusError(
                f"HTTP {resp.status_code} for {url}", request=resp.request, response=resp
            )
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            last_error = e
        if attempt < MAX_ATTEMPTS:
            time.sleep(_retry_delay(resp, attempt))
    raise last_error if last_error else RuntimeError(f"fetch failed: {url}")
