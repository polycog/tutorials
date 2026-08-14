"""An in-memory chat transcript between the human at the TUI and a remote agent.

Kept separate from SmartHomeEnvironment: chat isn't a device, and unlike device state
it's append-only history rather than a single current reading.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Source = Literal["human", "agent"]


class ChatMessage(TypedDict):
    source: Source
    text: str
    processed: bool


class ChatTranscript:
    """The full history of a chat, in order sent.

    Only human messages carry meaningful "processed" state: it tracks whether the agent
    has explicitly acknowledged the latest one, via acknowledge_latest_human_message().
    Reading a message doesn't process it — only that call does — so an agent can poll
    latest_human_message() as many times as it likes without losing track of whether it
    has actually dealt with what's there. An agent's own messages need no
    acknowledgment, so they're always recorded as already processed.
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []

    @property
    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

    def add(self, source: Source, text: str) -> ChatMessage:
        message: ChatMessage = {"source": source, "text": text, "processed": source != "human"}
        self._messages.append(message)
        return message

    def latest_human_message(self) -> ChatMessage | None:
        """The most recently sent human message, or None if there's never been one."""
        for message in reversed(self._messages):
            if message["source"] == "human":
                return message
        return None

    def acknowledge_latest_human_message(self) -> ChatMessage | None:
        """Explicitly mark the latest human message as processed, so it stops being
        surfaced as new. Idempotent — acknowledging an already-processed message just
        returns it unchanged. Returns None if there's no human message yet."""
        message = self.latest_human_message()
        if message is not None:
            message["processed"] = True
        return message
