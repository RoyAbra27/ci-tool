"""HTTP layer: every outbound request goes through one function with bounded
retries that honor Retry-After. Nothing else in the package calls httpx."""

import time

import httpx

TIMEOUT = 10.0
MAX_ATTEMPTS = 3
RETRYABLE = {429, 500, 502, 503, 504}
UA = "ci-tool/0.1 (competitive-intelligence pipeline)"


def _retry_delay(resp: httpx.Response | None, attempt: int) -> float:
    if resp is not None:
        ra = resp.headers.get("retry-after", "")
        if ra.replace(".", "", 1).isdigit():
            return min(float(ra), 90.0)
    return float(2**attempt)


def _request(method: str, url: str, *, params=None, json_body=None, headers=None,
             timeout: float = TIMEOUT) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        resp = None
        try:
            resp = httpx.request(
                method, url, params=params, json=json_body,
                headers={"User-Agent": UA, **(headers or {})},
                timeout=timeout, follow_redirects=True,
            )
        except httpx.HTTPError as e:
            last_error = e
        else:
            if resp.status_code < 400:
                return resp
            # a non-retryable status will not fix itself on attempt two
            if resp.status_code not in RETRYABLE:
                resp.raise_for_status()
            last_error = httpx.HTTPStatusError(
                f"HTTP {resp.status_code} for {url}", request=resp.request, response=resp
            )
        if attempt < MAX_ATTEMPTS:
            time.sleep(_retry_delay(resp, attempt))
    raise last_error if last_error else RuntimeError(f"fetch failed: {url}")


def get_text(url: str, *, params: dict | None = None) -> str:
    return _request("GET", url, params=params).text


def post_json(url: str, *, params=None, json_body=None, headers=None,
              timeout: float = 60.0) -> dict:
    return _request("POST", url, params=params, json_body=json_body,
                    headers=headers, timeout=timeout).json()
