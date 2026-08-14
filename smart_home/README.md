# smart_home

A minimal simulated smart home for exercising an agent's ability to observe and act on
an environment. Two simulation modes are built in. Use it in-process, or run the
included terminal control panel and drive it remotely over HTTP from any agent, in any
language.

## Modes

| Mode        | Devices                                                                                                                         |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `simple`     | one room: `lamp` (light)                                                                                                         |
| `realistic`  | `bedroom`, `living_room`, `kitchen`, `bathroom` (lights); `main_door` (lock); `dishwasher` (in the kitchen); `washer`, `dryer`, `laundry_basket` (in the laundry) |

Lights support `turn_on`/`turn_off`; the lock supports `lock`/`unlock` and starts locked;
appliances (dishwasher, washer, dryer) support `start`/`stop` and start idle; the laundry
basket supports `fill`/`empty` and starts empty.

Devices are addressed individually (there's no "room" concept in the environment or the
API), but the TUI groups them visually into rooms: `living_room` + `main_door` share a
panel, as do `kitchen` + `dishwasher`; `washer` + `dryer` + `laundry_basket` share a
`laundry` panel with no light of its own.

## Contents

```
smart_home/
├── devices.py       Light, Switch, Lock, Appliance, Basket — the physical model
├── sensors.py        LampSensor, LockSensor, ApplianceSensor, BasketSensor — read device state
├── environment.py     SmartHomeEnvironment, Observation, Action, Mode, KIND_ACTIONS
├── chat.py             ChatTranscript, ChatMessage — the human/agent chat history
├── rooms.py            room-grouping/label metadata for the TUI
├── api.py              Flask-RESTful API factory + server start/stop
├── ipc.py              HOST/PORT constants for the remote API
├── client.py            SmartHomeClient — reference HTTP client for a remote agent to observe/act/chat
├── example.py           small demo built on SmartHomeClient — see "Connecting an agent" below
├── smart_home.py       SmartHome — Textual TUI
├── smart_home.tcss      stylesheet for the TUI
├── requirements.txt
└── tests/
```

## Install

```
pip install -r smart_home/requirements.txt
```

## Local use

Drive the environment directly in the same process — no server involved:

```python
from smart_home import SmartHomeEnvironment

env = SmartHomeEnvironment(mode="realistic")  # or "simple" (the default)
env.devices    # {'bedroom': 'light', ..., 'main_door': 'lock', 'dishwasher': 'appliance', ...}
env.observe()                          # {'bedroom': 'off', ..., 'main_door': 'locked', 'dishwasher': 'idle', ...}
env.actuate("kitchen", "turn_on")      # {'bedroom': 'off', ..., 'kitchen': 'on', ...}
env.actuate("main_door", "unlock")     # {..., 'main_door': 'unlocked'}
env.actuate("washer", "start")         # {..., 'washer': 'running'}
env.actuate("laundry_basket", "fill")  # {..., 'laundry_basket': 'full'}
```

## Remote use

Run the TUI, which shows every device's state live, has a chat panel for talking to
a connected agent, and also hosts a Flask-RESTful API on `127.0.0.1:8765` (see
`ipc.py`) so a separate agent process can observe/act on the same running environment
and read/send chat messages:

```
python3 smart_home/smart_home.py                  # simple mode (default)
python3 smart_home/smart_home.py --mode realistic  # all rooms, the main door, and the appliances
```

### API

| Method | Path           | Body                                      | Response                        |
|--------|----------------|--------------------------------------------|----------------------------------|
| GET    | `/observation` | —                                           | `{device: state, ...}`            |
| POST   | `/actuate`     | `{"device": ..., "action": ...}`            | `{device: state, ...}` (all devices) |
| GET    | `/chat`        | —                                           | `[{"source": "human"/"agent", "text": ..., "processed": bool}, ...]` (full transcript) |
| POST   | `/chat`        | `{"message": ...}`                          | `{"source": "agent", "text": ..., "processed": true}` (the message just added) |
| POST   | `/chat/ack`    | —                                           | the latest human message, now with `"processed": true` — or `null` if there isn't one yet |

`action` must be valid for that device's kind (`turn_on`/`turn_off` for a light,
`lock`/`unlock` for a lock, `start`/`stop` for an appliance, `fill`/`empty` for a
basket). An unknown `device` or an `action` invalid for it returns `400` with
`{"message": "..."}`. `POST /chat` always appends with source `"agent"` — messages the
human types into the TUI's chat panel appear in the transcript with source `"human"`.
An empty/missing `message` returns `400`.

Every chat message carries a `processed` flag. Agent messages are always `true` — an
agent's own words need no acknowledgment. A human message starts `false` and stays that
way, no matter how many times `GET /chat` is polled, until an agent calls
`POST /chat/ack`, which flips the *latest* human message to `true`. That's the only way
`processed` changes — it's explicit, not a side effect of reading.

### Connecting an agent

Any HTTP client works — the API is plain REST, so an agent isn't tied to a particular
language. `smart_home.client.SmartHomeClient` is a reference implementation using
`requests` (one possible way to connect, not part of the protocol itself — that's
`api.py`):

```python
from smart_home.client import SmartHomeClient

client = SmartHomeClient()
client.connect()                          # raises ConnectionError if nothing is listening
client.observe()                          # {'lamp': 'off'}  (or one entry per device in realistic mode)
client.actuate("lamp", "turn_on")         # {'lamp': 'on'}
client.get_message_history()              # [{"source": "human", "text": "turn on the lamp", "processed": False}]
client.get_last_message()                 # the latest human message, if not yet acknowledged — else None.
                                           # read-only: polling this in a loop keeps returning the same message
client.acknowledge_message()              # marks it processed, so get_last_message() stops returning it
client.send_message("sure, turning it on")  # {"source": "agent", "text": "sure, turning it on", "processed": True}
client.close()                            # or use `with client:` instead of calling close()
```

`example.py` is a small demo built on it that works against either mode. It prints the
chat transcript so far (`get_message_history()`), then waits — polling
`get_last_message()` — for the human to type a message into the TUI's chat panel,
printing it once it arrives, then explicitly acknowledges it (`acknowledge_message()`)
so it won't be surfaced again. It then reads whatever devices `observe()` returns and
toggles each one in turn, sending a chat message narrating each action as it goes
(`send_message()`). Run it against a live TUI with `python3 smart_home/example.py`.

## Tests

```
pytest smart_home
```
