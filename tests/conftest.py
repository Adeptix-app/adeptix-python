from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import pytest

Reply = Union[Tuple[int, Any], Exception]


class FakeTransport:
    """Stands in for the HTTP layer, like the Node tests' fake fetch and the PHP tests' transport.

    Each entry in ``replies`` is either ``(status, json_body_or_raw_bytes)`` or an exception to
    raise (simulating a network failure). The last reply repeats once the list is exhausted.
    """

    def __init__(self, *replies: Reply) -> None:
        self._replies: List[Reply] = list(replies)
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: Optional[bytes],
        timeout_s: float,
    ) -> Tuple[int, bytes]:
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "body": body, "timeout_s": timeout_s}
        )
        reply = self._replies[min(len(self.calls), len(self._replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        status, payload = reply
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        return status, raw

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def sent_json(self, index: int = -1) -> Any:
        body = self.calls[index]["body"]
        return None if body is None else json.loads(body)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> List[float]:
    """Record backoff sleeps instead of actually sleeping."""
    recorded: List[float] = []
    monkeypatch.setattr("adeptix.client.time.sleep", lambda s: recorded.append(s))
    return recorded
