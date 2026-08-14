import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smart_home.client import SmartHomeClient

# Maps a device's current state to the action that flips it, so this demo works
# unmodified against both simple mode and realistic mode, whatever devices they have.
TOGGLE_ACTION = {
    "off": "turn_on",
    "on": "turn_off",
    "locked": "unlock",
    "unlocked": "lock",
    "idle": "start",
    "running": "stop",
}

client = SmartHomeClient()
try:
    client.connect()
except ConnectionError as exc:
    raise SystemExit(exc)

with client:
    transcript = client.get_message_history()
    print(f"Chat so far ({len(transcript)} message(s)):")
    for message in transcript:
        print(f"  {message['source']}: {message['text']}")

    # Wait for the human to type something into the TUI's chat panel, polling for an
    # unprocessed message from them — this is how an agent notices a human said
    # something rather than just narrating its own actions. get_last_message() is
    # read-only, so it keeps returning the same message every time it's polled...
    print("Type a message in the TUI's chat panel to continue...")
    message = None
    while message is None:
        message = client.get_last_message()
        if message is None:
            time.sleep(0.5)
    print(f"  human: {message['text']}")

    # ...until the agent explicitly acknowledges it. Without this, get_last_message()
    # would keep surfacing the same message forever.
    client.acknowledge_message()
    print("Acknowledged. get_last_message() now returns:", client.get_last_message())

    observation = client.observe()
    print(observation)  # {'lamp': 'off'} in simple mode, one entry per device in realistic mode

    for device, state in observation.items():
        action = TOGGLE_ACTION[state]
        input(f"Press Enter to {action} {device}...")
        observation = client.actuate(device, action)
        print(observation)
        # Narrate the action into the chat panel, same as a real agent would explain
        # itself to the human watching the TUI.
        client.send_message(f"{action} {device} -> now {observation[device]}")
