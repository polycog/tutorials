"""Room/label metadata for the TUI.

The environment and its API address devices individually — there's no "room" concept
below this layer. Grouping devices into rooms, and picking human-readable labels, is a
presentation-only concern, so it lives here rather than in environment.py.
"""

from __future__ import annotations

from typing import Literal

DEVICE_LABELS = {
    "main_door": "Main Door",
    "dishwasher": "Dishwasher",
    "washer": "Washer",
    "dryer": "Dryer",
    "laundry_basket": "Laundry Basket",
}

ROOM_LABELS = {
    "lamp": "Smart Home 01",
    "bedroom": "Bedroom",
    "living_room": "Living Room",
    "kitchen": "Kitchen",
    "bathroom": "Bathroom",
    "laundry": "Laundry",
}

# Which devices are grouped into which room panel, per mode, and how they're laid out
# within it: each room maps to a tuple of rows, and each row is a tuple of one or more
# devices shown side by side (e.g. laundry's washer/dryer share a row; laundry_basket
# gets its own row below them). Room order is row-major left-to-right, top-to-bottom
# over that mode's ROOM_GRID_SIZE — e.g. realistic mode's 2-column grid places
# bedroom/living_room in row 1 and bathroom/kitchen in row 2.
ROOM_DEVICES = {
    "simple": (("lamp", (("lamp",),)),),
    "realistic": (
        ("bedroom", (("bedroom",),)),
        ("living_room", (("living_room",), ("main_door",))),
        ("bathroom", (("bathroom",),)),
        ("kitchen", (("kitchen",), ("dishwasher",))),
        ("laundry", (("washer", "dryer"), ("laundry_basket",))),
    ),
}

# (columns, rows) for the #home grid, per mode.
ROOM_GRID_SIZE = {"simple": (1, 1), "realistic": (2, 3)}

# How many grid columns a room panel occupies, per mode. Rooms not listed span 1.
ROOM_COLUMN_SPAN = {"realistic": {"laundry": 2}}

# Which state counts as "engaged" (switch on / light lit / door locked / appliance
# running / basket full) vs "notable" (worth flagging — on, running, full, or
# *unlocked*).
KIND_ENGAGED_STATE = {"light": "on", "lock": "locked", "appliance": "running", "basket": "full"}
KIND_NOTABLE_STATE = {"light": "on", "lock": "unlocked", "appliance": "running", "basket": "full"}


def room_label(room_id: str) -> str:
    return ROOM_LABELS.get(room_id, room_id.replace("_", " ").title())


def device_line_label(device: str, kind: Literal["light", "lock", "appliance"]) -> str:
    if kind == "light":
        return "Light"
    return DEVICE_LABELS.get(device, device.replace("_", " ").title())
