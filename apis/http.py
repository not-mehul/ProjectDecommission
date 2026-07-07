"""Shared HTTP session construction for the API clients.

Previously each client configured only half of the reliability story: the
external client mounted a retry adapter but passed no timeout, while the
internal client passed a per-call timeout but had no retry adapter. A retry
adapter alone does NOT impose a socket timeout — a peer that accepts the
connection then never responds hangs forever, pinning one of the executor's
few worker threads. `build_session()` gives both clients a single Session that
carries retries AND a default connect/read timeout, closing that gap in one
place.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from constants import DEFAULT_TIMEOUT


class _TimeoutRetryAdapter(HTTPAdapter):
    """HTTPAdapter that applies a default timeout when a caller omits one.

    `Retry` handles transient status/connection failures but leaves the socket
    timeout unset. Injecting a default here means every request through the
    session is bounded, without having to thread `timeout=` through each call
    site (callers that pass their own `timeout` still win).
    """

    def __init__(self, *args, timeout: float = DEFAULT_TIMEOUT, **kwargs) -> None:
        self._timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self._timeout
        return super().send(request, **kwargs)


def build_session(timeout: float = DEFAULT_TIMEOUT) -> requests.Session:
    """Return a Session with retry + a default timeout mounted on http/https."""
    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={"POST", "GET", "DELETE", "PUT"},
    )
    adapter = _TimeoutRetryAdapter(max_retries=retries, timeout=timeout)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
