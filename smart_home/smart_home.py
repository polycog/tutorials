from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.theme import Theme
from textual.widgets import Footer, Header, Input, RichLog, Static, Switch
from werkzeug.serving import BaseWSGIServer

from smart_home import SmartHomeEnvironment
from smart_home.api import build_api, start_api_server, stop_api_server
from smart_home.chat import ChatMessage, ChatTranscript
from smart_home.environment import KIND_ACTIONS, Mode, Observation
from smart_home.ipc import HOST, PORT
from smart_home.rooms import (
    KIND_ENGAGED_STATE,
    KIND_NOTABLE_STATE,
    ROOM_COLUMN_SPAN,
    ROOM_DEVICES,
    ROOM_GRID_SIZE,
    device_line_label,
    room_label,
)

PURPLE_THEME = Theme(
    name="smart-home",
    primary="#8b5cf6",
    secondary="#6d28d9",
    accent="#c084fc",
    warning="#ffb545",
    success="#34d399",
    error="#f87171",
    dark=True,
)

# A distinct little ASCII icon per device kind (filled = engaged), so devices are
# recognizable at a glance even without reading the label. Kept to 3 lines each —
# tall enough to read as art, short enough that a full room of panels still fits
# on one screen. Lamps are circular; the lock and appliance boxes stay square/blocky;
# the basket has handles above an open body, so all four kinds stay visually distinct.
LAMP_OFF = """\
.-.
(○)
'-'"""

LAMP_ON = """\
.-.
(●)
'-'"""

DOOR_UNLOCKED = """\
▛▀▜
▌◇▐
▙▄▟"""

DOOR_LOCKED = """\
▛▀▜
▌◆▐
▙▄▟"""

APPLIANCE_IDLE = """\
┌─┐
│□│
└─┘"""

APPLIANCE_RUNNING = """\
┌─┐
│■│
└─┘"""

BASKET_EMPTY = """\
n n
[_]
▔▔▔"""

BASKET_FULL = """\
n n
[≈]
▔▔▔"""

KIND_ICONS = {
    "light": (LAMP_OFF, LAMP_ON),
    "lock": (DOOR_UNLOCKED, DOOR_LOCKED),
    "appliance": (APPLIANCE_IDLE, APPLIANCE_RUNNING),
    "basket": (BASKET_EMPTY, BASKET_FULL),
}

# Who a session-history line is attributed to.
SOURCE_TAGS = {"tui": "you", "agent": "agent", "system": "system"}

MIN_ROOM_WIDTH = 22  # keep in sync with .room-panel's min-width in smart_home.tcss


class SmartHome(App):
    """A terminal control panel for smart_home.SmartHomeEnvironment.

    Also hosts the environment, and a chat transcript, behind a Flask-RESTful API (see
    smart_home.api) so a separate process (see example.py) can connect, actuate the
    same running smart home, and chat with the human at the TUI, all as a remote agent.
    """

    CSS_PATH = "smart_home.tcss"
    TITLE = "smart_home"

    BINDINGS = [
        Binding("s", "toggle_switch", "Toggle switch"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, mode: Mode = "simple", host: str = HOST, port: int = PORT) -> None:
        super().__init__()
        self.env = SmartHomeEnvironment(mode=mode)
        self.chat = ChatTranscript()
        self.host = host
        self.port = port
        self.api_app = build_api(
            self.env,
            self.chat,
            after_observe=self._after_observe,
            after_actuate=self._after_actuate,
            after_chat=self._after_chat,
        )
        self._server: BaseWSGIServer | None = None
        self._server_thread: threading.Thread | None = None
        self._suppress_switch_events: set[str] = set()
        self.sub_title = f"{mode} mode"
        self.register_theme(PURPLE_THEME)
        self.theme = "smart-home"

    def _after_observe(self, observation: Observation, remote_addr: str) -> None:
        # Runs on a Flask worker thread; hop onto the Textual thread before touching widgets.
        self.call_from_thread(self.log_call, "observe()", observation, source="agent")

    def _after_actuate(self, device: str, action: str, observation: Observation, remote_addr: str) -> None:
        self.call_from_thread(self._sync_after_remote_actuate, device, action, observation)

    def _sync_after_remote_actuate(self, device: str, action: str, observation: Observation) -> None:
        self.sync_switch(device, self._engaged(device, observation[device]))
        self.reflect(device, action, observation, source="agent")

    def _after_chat(self, message: ChatMessage, remote_addr: str) -> None:
        self.call_from_thread(self.write_chat_message, message)

    def compose(self) -> ComposeResult:
        yield Header()
        observation = self.env.observe()
        with Horizontal(id="body"):
            with Container(id="home"):
                with Container(id="room-grid") as room_grid:
                    columns, rows = ROOM_GRID_SIZE[self.env.mode]
                    room_grid.styles.grid_size_columns = columns
                    room_grid.styles.grid_size_rows = rows
                    # A floor on the grid's own width, so narrow terminals scroll the
                    # room grid horizontally instead of squeezing every panel to nothing.
                    room_grid.styles.min_width = columns * MIN_ROOM_WIDTH + (columns - 1)
                    for room_id, device_rows in ROOM_DEVICES[self.env.mode]:
                        yield from self._room_panel(room_id, device_rows, observation)
            with Vertical(id="controls"):
                yield Static("Events", id="log-label")
                yield RichLog(id="log", markup=True, auto_scroll=True)
            with Vertical(id="chat"):
                yield Static("Chat", id="chat-label")
                yield RichLog(id="chat-log", markup=True, auto_scroll=True, wrap=True)
                yield Input(placeholder="Message the agent…", id="chat-input")
        yield Footer()

    def _room_panel(
        self, room_id: str, device_rows: tuple[tuple[str, ...], ...], observation: dict
    ) -> ComposeResult:
        # One bordered panel per room; one row per tuple in device_rows, with the
        # devices in that row placed side by side (e.g. laundry's washer + dryer).
        # The room name sits in the border itself rather than its own line, to
        # keep every panel as short as possible.
        panel = Vertical(id=f"panel-{room_id}", classes="room-panel")
        panel.border_title = room_label(room_id)
        panel.styles.column_span = ROOM_COLUMN_SPAN.get(self.env.mode, {}).get(room_id, 1)
        with panel:
            for devices in device_rows:
                with Horizontal(classes="device-row"):
                    for device in devices:
                        yield from self._device_line(device, observation[device])

    def _device_line(self, device: str, state: str) -> ComposeResult:
        kind = self.env.devices[device]
        with Horizontal(classes="device-line"):
            icon = Static(self._icon(device, state), id=f"icon-{device}", classes="device-icon")
            icon.set_class(self._notable(device, state), "notable")
            yield icon
            with Vertical(classes="device-info"):
                yield Static(device_line_label(device, kind), classes="device-name")
                yield Switch(value=self._engaged(device, state), id=f"switch-{device}", classes="device-switch")

    async def on_mount(self) -> None:
        self.log_call("reset()", self.env.observe())
        try:
            self.start_server()
        except OSError as exc:
            self.notify(f"Remote control disabled: {exc}", severity="error", timeout=8)

    async def on_unmount(self) -> None:
        if self._server is not None:
            stop_api_server(self._server, self._server_thread)

    def start_server(self) -> None:
        self._server, self._server_thread = start_api_server(self.api_app, self.host, self.port)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id or ""
        if not switch_id.startswith("switch-"):
            return
        device = switch_id.removeprefix("switch-")
        if device in self._suppress_switch_events:
            return
        on_action, off_action = KIND_ACTIONS[self.env.devices[device]]
        self.actuate(device, on_action if event.value else off_action)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        if not text:
            return
        self.send_human_message(text)
        event.input.value = ""

    def send_human_message(self, text: str) -> ChatMessage:
        message = self.chat.add("human", text)
        self.write_chat_message(message)
        return message

    def write_chat_message(self, message: ChatMessage) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        tag = "[bold]you[/bold]" if message["source"] == "human" else "[dim]agent[/dim]"
        chat_log.write(f"{tag} · {message['text']}")

    def sync_switch(self, device: str, engaged: bool) -> None:
        self._suppress_switch_events.add(device)
        self.query_one(f"#switch-{device}", Switch).value = engaged
        self._suppress_switch_events.discard(device)

    def actuate(self, device: str, action: str) -> None:
        observation = self.env.actuate(device, action)
        self.reflect(device, action, observation)

    def reflect(self, device: str, action: str, observation: dict, source: str = "tui") -> None:
        self._update_panel(device, observation[device])
        self.log_call(f"actuate({device!r}, {action!r})", observation, source=source)

    def _engaged(self, device: str, state: str) -> bool:
        kind = self.env.devices[device]
        return state == KIND_ENGAGED_STATE[kind]

    def _icon(self, device: str, state: str) -> str:
        kind = self.env.devices[device]
        off_art, on_art = KIND_ICONS[kind]
        return on_art if self._engaged(device, state) else off_art

    def _notable(self, device: str, state: str) -> bool:
        kind = self.env.devices[device]
        return state == KIND_NOTABLE_STATE[kind]

    def _update_panel(self, device: str, state: str) -> None:
        icon = self.query_one(f"#icon-{device}", Static)
        icon.update(self._icon(device, state))
        icon.set_class(self._notable(device, state), "notable")

    def log_call(self, call_text: str, observation: dict, source: str = "tui") -> None:
        log = self.query_one("#log", RichLog)
        tag = "[dim]agent ·[/dim] " if source == "agent" else ""
        log.write(f"{tag}[dim]>[/dim] {call_text}")
        for device, state in observation.items():
            notable = self._notable(device, state)
            color = "yellow" if notable else "white"
            log.write(f"  {device}=[{color}]{state!r}[/{color}]")

    def action_toggle_switch(self) -> None:
        device = next(iter(self.env.devices))
        switch = self.query_one(f"#switch-{device}", Switch)
        switch.value = not switch.value


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the smart_home TUI.")
    parser.add_argument("--mode", choices=["simple", "realistic"], default="simple")
    args = parser.parse_args()
    SmartHome(mode=args.mode).run()
