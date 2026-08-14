"""Smart home agent demonstrating hierarchical decision processes."""

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, cast

from cognition import (
    Actuator,
    AutoDocEnum,
    Cogent,
    DecisionProcess,
    DocEnum,
    IOContainer,
    Operator,
    Sensor,
)
from cognition.language import EnumClassifier
from pydantic import BaseModel
from pydantic_ai.models import infer_model

from smart_home.client import SmartHomeClient
from utils import run_cogent

# =============================================================================
# Enums & Data Models
# =============================================================================


class Devices(DocEnum):
    """Smart home device taxonomy."""

    BEDROOM = "bedroom", "light device in the bedroom"
    LIVING_ROOM = "living_room", "light device in the living room"
    KITCHEN = "kitchen", "light device in the kitchen"
    BATHROOM = "bathroom", "light device in the bathroom"
    MAIN_DOOR = "main_door", "main door lock device in living room"
    DISHWASHER = "dishwasher", "dishwasher device in kitchen"
    WASHER = "washer", "washing machine, washer in laundry room"
    DRYER = "dryer", "drying machine, dryer in laundry room"
    LAUNDRY_BASKET = "laundry_basket", "laundry basket device in laundry room"


LIGHTS = {
    Devices.BATHROOM,
    Devices.BEDROOM,
    Devices.KITCHEN,
    Devices.LIVING_ROOM,
    Devices.LAUNDRY_BASKET,
}

LOCKS = {Devices.MAIN_DOOR}

RUNNABLES = {Devices.WASHER, Devices.DRYER, Devices.DISHWASHER}


class DeviceState(StrEnum):
    """Smart home device operational states."""

    ON = "on"
    OFF = "off"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    IDLE = "idle"
    RUNNING = "running"
    EMPTY = "empty"
    FULL = "full"


class ControlSignal(StrEnum):
    """Control signals for smart home devices."""

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    START = "start"
    STOP = "stop"
    FILL = "fill"
    EMPTY = "empty"
    LOCK = "lock"
    UNLOCK = "unlock"


class ResidentIntent(DocEnum):
    """Supported resident intent categories."""

    TURN_OFF = (
        "turn_off",
        "user is asking the assistant to turn a device off or stop a device",
    )
    TURN_ON = (
        "turn_on",
        "user is asking the assistant to turn a device on or start a device",
    )
    LOCK = "lock", "user is asking the assistant to lock a device"
    UNLOCK = "unlock", "user is asking the assistant to unlock a device"
    SET_MODE = "set_mode", "user is asking the assistant to set an operational mode"


class MyIntent(StrEnum):
    """Standard conversational responses from the assistant."""

    DONTKNOW = "I am sorry; I am not programmed to respond to that."
    CONFIRMATION = "Done."


class Mode(AutoDocEnum):
    """Operating modes for the home assistant."""

    DAY = "day mode of smart assistant"
    EVENING = "evening mode of smart assistant"
    MIDNIGHT = "midnight mode of smart assistant"


class Observation(BaseModel, frozen=True):
    """State observation payload across all environment devices."""

    bedroom: Literal[DeviceState.ON, DeviceState.OFF]
    living_room: Literal[DeviceState.ON, DeviceState.OFF]
    kitchen: Literal[DeviceState.ON, DeviceState.OFF]
    bathroom: Literal[DeviceState.ON, DeviceState.OFF]
    main_door: Literal[DeviceState.LOCKED, DeviceState.UNLOCKED]
    dishwasher: Literal[DeviceState.IDLE, DeviceState.RUNNING]
    washer: Literal[DeviceState.IDLE, DeviceState.RUNNING]
    dryer: Literal[DeviceState.IDLE, DeviceState.RUNNING]
    laundry_basket: Literal[DeviceState.EMPTY, DeviceState.FULL]


@dataclass(frozen=True)
class Action:
    """Command action payload targeting a specific device."""

    device: Devices
    signal: ControlSignal


@dataclass(frozen=True)
class Utterance:
    """Natural language chat message contract."""

    phrase: str | None


# =============================================================================
# Global Clients & Language Models
# =============================================================================

client = SmartHomeClient()
try:
    client.connect()
    print("Successfully connected to Smart Home Simulation!")
except ConnectionError as exc:
    raise SystemExit(
        "Connection failed. Ensure the simulation app is running in another terminal.\n"
        f"Details: {exc}"
    ) from exc

assert "OPENAI_API_KEY" in os.environ, "Environment variable OPENAI_API_KEY is not set."
llm_model = infer_model("openai:gpt-4o")

# =============================================================================
# Sensors & Actuators
# =============================================================================


class HumanInteraction(Sensor[Utterance | None], Actuator[Utterance, None]):
    """Sensor and actuator interface for user chat interactions."""

    @property
    def name(self) -> str:
        return "interaction"

    def sense(self) -> Utterance | None:
        """Fetch the latest message from the human."""
        message = client.get_last_message()
        if message:
            return Utterance(phrase=message["text"])
        return Utterance(phrase=None)

    def actuate(self, param: Utterance) -> None:
        """Send a response to the human."""
        client.acknowledge_message()
        if param.phrase:
            client.send_message(param.phrase)


class SmartHomeDevices(Sensor[Observation], Actuator[Action, None]):
    """I/O interface for physical home devices."""

    @property
    def name(self) -> str:
        return "devices"

    def sense(self) -> Observation:
        """Fetch real-time state telemetry from all devices."""
        response = client.observe()
        return Observation.model_validate(response)

    def actuate(self, param: Action) -> None:
        """Dispatch control commands to physical devices."""
        client.actuate(str(param.device), param.signal)


# =============================================================================
# DecisionProcess :ProcessHumanIntent: State, Operators, Termination check
# =============================================================================


class KState(AutoDocEnum):
    """Enum representing knowledge states"""

    UNKNOWN = "symbol representing that something is unknown"


@dataclass
class StructuredIntent:
    """Sub-state storing parsed intent category and target entity."""

    intent: ResidentIntent | KState | None = None
    object: Mode | Devices | KState | None = None


class ExtractIntent(Operator[StructuredIntent]):
    """
    Super-process operator: ProcessHumanIntent
    INIT: Instantiate an EnumClassifer for ResidentIntent
    WHEN: Intent has not been unclassified
    THEN: Classify user utterance into a ResidentIntent, KState.UNKNOWN if failed
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._interpreter = EnumClassifier(
            enum_type=ResidentIntent,
            task_desc="what is the resident asking the assistant to do",
        )

    def can_perform(self, state: StructuredIntent, io: IOContainer) -> bool:
        return state.intent is None

    def perform(self, state: StructuredIntent, io: IOContainer) -> None:
        utterance = cast(Utterance, io.a.utterance)
        intent = self._interpreter(utterance.phrase, llm=llm_model, num_trials=1)[0]
        state.intent = intent if intent else KState.UNKNOWN
        if state.intent is KState.UNKNOWN:
            state.object = KState.UNKNOWN
        print(
            f"--> [Process intent decision process] -> recognized intent as {state.intent}"
        )


class ExtractIntentDevice(Operator[StructuredIntent]):
    """
    Super-process operator: ProcessHumanIntent
    INIT: Instantiate an EnumClassifer for Device
    WHEN: Intent is ResidentIntent.TURN_OFF/TURN_ON and Object is None
    THEN: Classify user utterance into a Device, KState.UNKNOWN if failed
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._interpreter = EnumClassifier(
            enum_type=Devices, task_desc="which device is the resident referring to"
        )

    def can_perform(self, state: StructuredIntent, io: IOContainer) -> bool:
        return bool(
            state.intent in (ResidentIntent.TURN_OFF, ResidentIntent.TURN_ON)
            and not state.object
        )

    def perform(self, state: StructuredIntent, io: IOContainer) -> None:
        utterance = cast(Utterance, io.a.utterance)
        assert utterance.phrase, "expect parent operator to fill value"
        device = self._interpreter(utterance.phrase, llm_model, num_trials=1)[0]
        state.object = device if device else KState.UNKNOWN
        print(
            f"--> [Process intent decision process] -> recognized devices {state.object}"
        )


class ExtractIntentMode(Operator[StructuredIntent]):
    """
    Super-process operator: ProcessHumanIntent
    INIT: Instantiate an EnumClassifer for Mode
    WHEN: Intent is ResidentIntent.TURN_OFF/TURN_ON and Object is None
    THEN: Classify user utterance into a Mode, unknown if failed
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._mode_interpreter = EnumClassifier(
            enum_type=Mode,
            task_desc="which mode is the user wanting to set",
        )

    def can_perform(self, state: StructuredIntent, io: IOContainer) -> bool:
        return bool(state.intent is ResidentIntent.SET_MODE and not state.object)

    def perform(self, state: Any, io: IOContainer) -> None:
        utterance = cast(Utterance, io.a.utterance)
        assert utterance.phrase, "expect parent operator to fill value"
        mode = self._mode_interpreter(utterance.phrase, llm_model, num_trials=1)[0]
        state.object = mode if mode else KState.UNKNOWN
        print(
            f"--> [Process intent decision process] -> recognized mode as {state.object}"
        )


def is_process_human_intent_terminal(state: StructuredIntent, _io: IOContainer) -> bool:
    """Super-process operator: ProcessHumanIntent
    terminate decision process when both intent and object have been classified"""
    return state.intent is not None and state.object is not None


# =============================================================================
# Decision Process : Main : State, Operators
# =============================================================================


@dataclass
class HomeState:
    """Top-level state maintained by the agent."""

    mode: Mode
    timer_expires_at: float = 0.0

    # Language processing pipeline
    human_utterance: Utterance | None = None
    human_intent: StructuredIntent | None = None


class ProcessHumanIntent(Operator[HomeState]):
    """
    INIT: Instantiate DecisionProcess for language interpretation.
    WHEN: Raw utterance exists but structured human intent is not populated.
    THEN: Invoke child DecisionProcess to extract a fully resolved StructuredIntent.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._human_utternace: Utterance | None = None
        self._dp: DecisionProcess[StructuredIntent] = DecisionProcess(StructuredIntent)
        self._dp.add_operator(ExtractIntent("extract_intent_class"))
        self._dp.add_operator(ExtractIntentDevice("extract_intent_device"))
        self._dp.add_operator(ExtractIntentMode("extract_intent_mode"))
        self._dp.add_termination_check(is_process_human_intent_terminal)

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        self._human_utternace = cast(Utterance, io.i.interaction)
        return bool(self._human_utternace.phrase and not state.human_intent)

    def perform(self, state: HomeState, io: IOContainer) -> None:
        print("--> [Interpret Intent triggered]")
        self._dp.reinit()
        state.human_intent = self._dp(utterance=self._human_utternace)
        print(f"--> [Interpreted Intent] human expressed: {state.human_intent}")


class ReportUnknownIntent(Operator[HomeState]):
    """
    WHEN: human_intent is unknown
    THEN: inform the user
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent:
            return (
                state.human_intent.intent is KState.UNKNOWN
                or state.human_intent.object is KState.UNKNOWN
            )
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.interaction(Utterance(phrase=MyIntent.DONTKNOW))
        state.human_intent = None
        state.human_utterance = None


class ActuateLightDevice(Operator[HomeState]):
    """
    WHEN: human_intent.intent is ResidentIntent.TURN_ON/TURN_OFF and
    human_intent.object a LIGHT device
    THEN: Dispatch appropriate control signal
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._device: Devices | None = None
        self._signal: ControlSignal | None = None

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if (
            state.human_intent
            and isinstance(state.human_intent.object, Devices)
            and state.human_intent.object in LIGHTS
        ):
            self._device = cast(Devices, state.human_intent.object)
            if state.human_intent.intent is ResidentIntent.TURN_ON:
                self._signal = ControlSignal.TURN_ON
            elif state.human_intent.intent is ResidentIntent.TURN_OFF:
                self._signal = ControlSignal.TURN_OFF
            return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(Action(device=self._device.value, signal=self._signal))
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Action Triggered] Dispatching device signal.")
        state.human_intent = None
        state.human_utterance = None


class ActuateRunnableDevice(Operator[HomeState]):
    """
    WHEN: human_intent.intent is ResidentIntent.TURN_ON/TURN_OFF and
    human_intent.object a RUNNABLE evice
    THEN: Dispatch appropriate control signal
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._device: Devices | None = None
        self._signal: ControlSignal | None = None

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if (
            state.human_intent
            and isinstance(state.human_intent.object, Devices)
            and state.human_intent.object in RUNNABLES
        ):
            self._device = cast(Devices, state.human_intent.object)
            if state.human_intent.intent is ResidentIntent.TURN_ON:
                self._signal = ControlSignal.START
            elif state.human_intent.intent is ResidentIntent.TURN_OFF:
                self._signal = ControlSignal.STOP
            return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(Action(device=self._device.value, signal=self._signal))
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Action Triggered] Dispatching device signal.")
        state.human_intent = None
        state.human_utterance = None


class ActuateLockDevice(Operator[HomeState]):
    """
    WHEN: human_intent.intent is ResidentIntent.TURN_ON/TURN_OFF and
    human_intent.object a LOCK device
    THEN: Dispatch appropriate control signal
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._device: Devices | None = None
        self._signal: ControlSignal | None = None

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if (
            state.human_intent
            and isinstance(state.human_intent.object, Devices)
            and state.human_intent.object in LOCKS
        ):
            self._device = cast(Devices, state.human_intent.object)
            if state.human_intent.intent is ResidentIntent.LOCK:
                self._signal = ControlSignal.LOCK
            elif state.human_intent.intent is ResidentIntent.UNLOCK:
                self._signal = ControlSignal.UNLOCK
            return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(Action(device=self._device.value, signal=self._signal))
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Action Triggered] Dispatching device signal.")
        state.human_intent = None
        state.human_utterance = None


class SetMode(Operator[HomeState]):
    """
    WHEN: Intent targets a system Mode change.
    THEN: Update internal system mode.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._mode: Mode | None = None

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent and (
            state.human_intent.intent is ResidentIntent.SET_MODE
            and isinstance(state.human_intent.object, Mode)
        ):
            self._mode = state.human_intent.object
            return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        state.mode = self._mode
        print(f"--> [Internal Action Triggered] Setting mode to {state.mode}")
        state.human_intent = None
        state.human_utterance = None
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))


# =============================================================================
# Agent Setup & Main Loop
# =============================================================================


def main() -> None:
    """Initialize and start the smart home agent."""
    state = HomeState(mode=Mode.MIDNIGHT)
    dp = DecisionProcess[HomeState](lambda: state)

    assistant: Cogent[DecisionProcess[HomeState]] = Cogent(decision_process=dp)
    devices = SmartHomeDevices()
    interaction = HumanInteraction()
    assistant.add_sensor(devices).add_actuator(devices)
    assistant.add_sensor(interaction).add_actuator(interaction)
    assistant.dp.add_operator(ProcessHumanIntent("process_human_input"))
    assistant.dp.add_operator(
        ReportUnknownIntent("report_unknown_intent", terminal=True)
    )
    assistant.dp.add_operator(SetMode("set_mode", terminal=True))
    assistant.dp.add_operator(ActuateLightDevice("actuate_light_device", terminal=True))
    assistant.dp.add_operator(
        ActuateRunnableDevice("actuate_runnable_device", terminal=True)
    )
    assistant.dp.add_operator(ActuateLockDevice("actuate_lock_device", terminal=True))

    run_cogent(assistant)


if __name__ == "__main__":
    main()
