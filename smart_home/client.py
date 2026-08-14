"""Reference HTTP client for talking to a running smart_home.smart_home.SmartHome server.

One possible way for an agent to connect, not part of the environment/protocol itself
(that's api.py) — an agent is free to speak the HTTP API directly instead.
"""

from __future__ import annotations

import socket
from types import TracebackType

import requests

from .ipc import HOST, PORT


class SmartHomeClient:
    """A connection to a running smart home server, plus its observe/actuate/chat calls.

    Usage:
        client = SmartHomeClient()
        try:
            client.connect()
        except ConnectionError as exc:
            raise SystemExit(exc)
        with client:
            client.observe()
    """

    def __init__(self, host: str = HOST, port: int = PORT, timeout: float = 1) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self.session: requests.Session | None = None

    def connect(self) -> SmartHomeClient:
        """Confirm a smart home server is reachable and open a session to it.

        Returns self, so construction and connection can chain:
        `client = SmartHomeClient().connect()`.
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout):
                pass
        except OSError as exc:
            raise ConnectionError(
                f"No running smart home environment at {self.base_url}. "
                "Start one with: python3 smart_home/smart_home.py"
            ) from exc
        self.session = requests.Session()
        return self

    def close(self) -> None:
        """Close the underlying session, if one is open."""
        if self.session is not None:
            self.session.close()
            self.session = None

    def __enter__(self) -> SmartHomeClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _require_session(self) -> requests.Session:
        if self.session is None:
            raise RuntimeError("not connected — call connect() first")
        return self.session

    def observe(self) -> dict:
        """Return the current state of every device, e.g. {"lamp": "off"}."""
        response = self._require_session().get(f"{self.base_url}/observation")
        response.raise_for_status()
        return response.json()

    def actuate(self, device: str, action: str) -> dict:
        """Act on one device (e.g. actuate("kitchen", "turn_on")) and return the
        resulting state of every device."""
        response = self._require_session().post(
            f"{self.base_url}/actuate", json={"device": device, "action": action}
        )
        response.raise_for_status()
        return response.json()

    def get_message_history(self) -> list[dict]:
        """Return the full chat transcript so far, e.g.
        [{"source": "human", "text": "hi", "processed": True}]."""
        return self._fetch_history()

    def get_last_message(self) -> dict | None:
        """Return the latest human message, if the agent hasn't acknowledged it yet
        (see acknowledge_message()) — or None if there isn't one, or it's already been
        acknowledged.

        A read-only check: calling this repeatedly keeps returning the same message
        until acknowledge_message() is called, so polling in a loop is safe.
        """
        for message in reversed(self._fetch_history()):
            if message["source"] == "human":
                return None if message["processed"] else message
        return None

    def acknowledge_message(self) -> dict | None:
        """Explicitly mark the latest human message as processed, so get_last_message()
        stops returning it. Returns the acknowledged message, or None if there's no
        human message yet."""
        response = self._require_session().post(f"{self.base_url}/chat/ack")
        response.raise_for_status()
        return response.json()

    def _fetch_history(self) -> list[dict]:
        response = self._require_session().get(f"{self.base_url}/chat")
        response.raise_for_status()
        return response.json()

    def send_message(self, message: str) -> dict:
        """Send a chat message as the agent, e.g. {"source": "agent", "text": message}."""
        response = self._require_session().post(f"{self.base_url}/chat", json={"message": message})
        response.raise_for_status()
        return response.json()
