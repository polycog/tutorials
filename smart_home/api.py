"""The Flask-RESTful API for a running SmartHomeEnvironment.

Kept separate from any particular frontend so the protocol is defined in exactly one
place — see client.py for the client side.
"""

from __future__ import annotations

import socket
import threading
from typing import Callable

from flask import Flask, request
from flask_restful import Api, Resource
from werkzeug.serving import BaseWSGIServer, make_server

from .chat import ChatMessage, ChatTranscript
from .environment import KIND_ACTIONS, Observation, SmartHomeEnvironment

# The str is the calling agent's remote address, so a frontend can notice a new agent.
AfterObserve = Callable[[Observation, str], None]
AfterActuate = Callable[[str, str, Observation, str], None]
AfterChat = Callable[[ChatMessage, str], None]


class ObservationResource(Resource):
    """GET /observation -> current state of every device."""

    def __init__(self, env: SmartHomeEnvironment, after_observe: AfterObserve | None) -> None:
        self.env = env
        self.after_observe = after_observe

    def get(self) -> Observation:
        observation = self.env.observe()
        if self.after_observe is not None:
            self.after_observe(observation, request.remote_addr or "unknown")
        return observation


class ActuateResource(Resource):
    """POST /actuate {"device": ..., "action": ...} -> resulting state of every device."""

    def __init__(self, env: SmartHomeEnvironment, after_actuate: AfterActuate | None) -> None:
        self.env = env
        self.after_actuate = after_actuate

    def post(self) -> tuple[dict, int] | Observation:
        payload = request.get_json(silent=True) or {}
        device = payload.get("device")
        action = payload.get("action")
        devices = self.env.devices
        if device not in devices:
            return {"message": f"Unknown device: {device!r}"}, 400
        if action not in KIND_ACTIONS[devices[device]]:
            return {"message": f"Unknown action: {action!r}"}, 400
        observation = self.env.actuate(device, action)
        if self.after_actuate is not None:
            self.after_actuate(device, action, observation, request.remote_addr or "unknown")
        return observation


class ChatResource(Resource):
    """GET /chat -> full transcript. POST /chat {"message": ...} -> agent sends a
    message, appended to the transcript with source "agent"."""

    def __init__(self, chat: ChatTranscript, after_chat: AfterChat | None) -> None:
        self.chat = chat
        self.after_chat = after_chat

    def get(self) -> list[ChatMessage]:
        return self.chat.messages

    def post(self) -> tuple[dict, int] | ChatMessage:
        payload = request.get_json(silent=True) or {}
        text = payload.get("message")
        if not isinstance(text, str) or not text.strip():
            return {"message": "message must be a non-empty string"}, 400
        message = self.chat.add("agent", text)
        if self.after_chat is not None:
            self.after_chat(message, request.remote_addr or "unknown")
        return message


class ChatAckResource(Resource):
    """POST /chat/ack -> agent explicitly acknowledges the latest human message,
    marking it processed so it won't be surfaced as new again. Returns the acknowledged
    message, or null if there's no human message yet."""

    def __init__(self, chat: ChatTranscript) -> None:
        self.chat = chat

    def post(self) -> ChatMessage | None:
        return self.chat.acknowledge_latest_human_message()


def build_api(
    env: SmartHomeEnvironment,
    chat: ChatTranscript,
    after_observe: AfterObserve | None = None,
    after_actuate: AfterActuate | None = None,
    after_chat: AfterChat | None = None,
) -> Flask:
    """A Flask app exposing GET /observation, POST /actuate, GET/POST /chat, and
    POST /chat/ack for `env` and `chat`.

    The optional hooks let a frontend react to remote-agent calls (e.g. to update its
    own display); they're irrelevant to the protocol itself.
    """
    app = Flask(__name__)
    api = Api(app)
    api.add_resource(
        ObservationResource, "/observation", resource_class_kwargs={"env": env, "after_observe": after_observe}
    )
    api.add_resource(
        ActuateResource, "/actuate", resource_class_kwargs={"env": env, "after_actuate": after_actuate}
    )
    api.add_resource(ChatResource, "/chat", resource_class_kwargs={"chat": chat, "after_chat": after_chat})
    api.add_resource(ChatAckResource, "/chat/ack", resource_class_kwargs={"chat": chat})
    return app


def start_api_server(app: Flask, host: str, port: int) -> tuple[BaseWSGIServer, threading.Thread]:
    """Start `app` on host:port in a daemon thread.

    Raises OSError if something is already listening there. make_server() swallows bind
    OSErrors internally (sys.exit(1)) instead of raising, so the port is probed directly
    first to detect a conflict cleanly.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise OSError(f"another smart home environment is already listening at {host}:{port}") from exc
    finally:
        probe.close()
    server = make_server(host, port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_api_server(server: BaseWSGIServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join()
