"""smart home assistant that can answer queries"""

import os
from dataclasses import dataclass, field
import time
from enum import Enum, StrEnum, auto
from typing import Any, Literal, cast, Iterable, Self

from cognition import (
    Actuator,
    AutoDocEnum,
    BinaryRelation,
    Cogent,
    DecisionProcess,
    DocEnum,
    Entity,
    EnumClassifier,
    IOContainer,
    ModelPopulator,
    Operator,
    Sensor,
    WorldGraph,
    describe_facts,
    OperatorGenerator,
)
from pydantic import BaseModel, Field
from pydantic_ai.models import infer_model

from smart_home.client import SmartHomeClient
from utils import run_cogent

#-------------------------------------------------------------------
# 1. Attributes: Affordances (Capabilities) & States
#-------------------------------------------------------------------


class DeviceType(Enum):
    """Immutable affordances defining what an entity can do."""

    LIGHTABLE = auto()
    LOCKABLE = auto()
    RUNNABLE = auto()
    MOVABLE = auto()
    FILLABLE = auto()


class DeviceState(StrEnum):
    """Mutable states reflecting current operational conditions."""

    ON = "on"
    OFF = "off"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    IDLE = "idle"
    RUNNING = "running"
    EMPTY = "empty"
    FULL = "full"


class DeviceName(StrEnum):
    """Standardized identifiers for known entities."""

    BEDROOM = "bedroom"
    LIVING_ROOM = "living_room"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    MAIN_DOOR = "main_door"
    DISHWASHER = "dishwasher"
    WASHER = "washer"
    LAUNDRY_BASKET = "laundry_basket"


# -------------------------------------------------------------------
# 2. Entities (Require a Unique Name upon Instantiation)
# -------------------------------------------------------------------


class Device(Entity):
    """Smart home device entity combining immutable affordances and mutable state.

    Inherits `name` from Entity, which must be uniquely specified at instantiation.
    """

    dtype: frozenset[DeviceType]  # Immutable affordances
    dstate: DeviceState  # Mutable state
    turn_off_at: float = 0.0


class Room(Entity):
    """Room entity.

    Requires a unique `name` string upon instantiation (e.g., Room(name="room:kitchen")).
    """


class RoomName(StrEnum):
    """Standardized identifiers for room nodes."""

    KITCHEN = "room:kitchen"
    LIVING_ROOM = "room:living"
    BEDROOM = "room:bed"
    BATHROOM = "room:bath"
    LAUNDRY = "room:laundry"


# -------------------------------------------------------------------
# 3. Relations (Defined Over Named Entities)
# -------------------------------------------------------------------


class In(BinaryRelation):
    """Directed relation linking a Device entity to a Room entity."""

    entity1: Device = Field(frozen=True)
    entity2: Room = Field(frozen=True)


def init_house_state() -> WorldGraph:
    """initialize a world graph corresponding to the smart home environment"""

    world = WorldGraph()
    # ---------------------------------------------------------------
    # 1. Bedroom Topology
    # ---------------------------------------------------------------
    bedroom = Room(name=RoomName.BEDROOM)
    bedroom_lamp = Device(
        name="bedroom",
        dtype=frozenset([DeviceType.LIGHTABLE]),
        dstate=DeviceState.ON,
    )
    world.add_entity(bedroom)
    world.add_entity(bedroom_lamp)
    world.add_relation(In(entity1=bedroom_lamp, entity2=bedroom))

    # ---------------------------------------------------------------
    # 2. Living Room Topology
    # ---------------------------------------------------------------
    living_room = Room(name=RoomName.LIVING_ROOM)
    living_room_lamp = Device(
        name="living_room",
        dtype=frozenset([DeviceType.LIGHTABLE]),
        dstate=DeviceState.ON,
    )
    main_door = Device(
        name="main_door",
        dtype=frozenset([DeviceType.LOCKABLE]),
        dstate=DeviceState.LOCKED,
    )
    world.add_entity(living_room)
    world.add_entity(living_room_lamp)
    world.add_entity(main_door)
    world.add_relation(In(entity1=living_room_lamp, entity2=living_room))
    world.add_relation(In(entity1=main_door, entity2=living_room))

    # ---------------------------------------------------------------
    # 3. Bathroom Topology
    # ---------------------------------------------------------------
    bathroom = Room(name=RoomName.BATHROOM)
    bathroom_lamp = Device(
        name="bathroom", dtype=frozenset([DeviceType.LIGHTABLE]), dstate=DeviceState.ON
    )
    world.add_entity(bathroom)
    world.add_entity(bathroom_lamp)
    world.add_relation(In(entity1=bathroom_lamp, entity2=bathroom))

    # ---------------------------------------------------------------
    # 4. Kitchen Topology
    # ---------------------------------------------------------------
    kitchen = Room(name=RoomName.KITCHEN)
    kitchen_lamp = Device(
        name="kitchen", dtype=frozenset([DeviceType.LIGHTABLE]), dstate=DeviceState.ON
    )

    dishwasher = Device(
        name="dishwasher",
        dtype=frozenset([DeviceType.RUNNABLE, DeviceType.FILLABLE]),
        dstate=DeviceState.RUNNING,
    )
    world.add_entity(kitchen)
    world.add_entity(kitchen_lamp)
    world.add_entity(dishwasher)
    world.add_relation(In(entity1=kitchen_lamp, entity2=kitchen))
    world.add_relation(In(entity1=dishwasher, entity2=kitchen))

    # ---------------------------------------------------------------
    # 5. Laundry Room Topology
    # ---------------------------------------------------------------
    laundry = Room(name=RoomName.LAUNDRY)
    washer = Device(
        name="washer",
        dtype=frozenset([DeviceType.RUNNABLE, DeviceType.FILLABLE]),
        dstate=DeviceState.IDLE,
    )
    dryer = Device(
        name="dryer",
        dtype=frozenset([DeviceType.RUNNABLE, DeviceType.FILLABLE]),
        dstate=DeviceState.IDLE,
    )
    laundry_basket = Device(
        name="laundry_basket",
        dtype=frozenset([DeviceType.MOVABLE, DeviceType.FILLABLE]),
        dstate=DeviceState.EMPTY,
    )
    world.add_entity(laundry)
    world.add_entity(washer)
    world.add_entity(dryer)
    world.add_entity(laundry_basket)
    world.add_relation(In(entity1=washer, entity2=laundry))
    world.add_relation(In(entity1=dryer, entity2=laundry))
    world.add_relation(In(entity1=laundry_basket, entity2=laundry))

    return world


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


@dataclass(frozen=True)
class Utterance:
    """Natural language chat message contract."""

    phrase: str | None


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


@dataclass(frozen=True)
class Action:
    """Command action payload targeting a specific device."""

    device: DeviceName
    signal: ControlSignal


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


class Mode(AutoDocEnum):
    """Operating modes for the home assistant."""

    DAY = "day mode of smart assistant"
    EVENING = "evening mode of smart assistant"
    MIDNIGHT = "midnight mode of smart assistant"


class KState(AutoDocEnum):
    """Enum representing knowledge states"""

    UNKNOWN = "symbol representing that something is unknown"


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
    GET_DEVICE_INFO = (
        "get_info",
        "user is asking the assistant to provide information about ",
    )
    "their devices"


class DeviceQuery(BaseModel):
    """base model describing the device query"""

    dtype: DeviceType | None
    dstate: DeviceState | None
    room: RoomName | None


@dataclass
class StructuredIntent:
    """Sub-state storing parsed intent category and target entity."""

    intent: ResidentIntent | KState | None = None
    object: Mode | DeviceName | DeviceQuery | KState | None = None


@dataclass
class HomeState:
    """Top-level state maintained by the agent."""

    mode: Mode
    timer_expires_at: float = 0.0

    # World model
    world: WorldGraph = field(default_factory=init_house_state)

    # Language processing pipeline
    human_utterance: Utterance | None = None
    human_intent: StructuredIntent | None = None

    #Times



class MyIntent(StrEnum):
    """Standard conversational responses from the assistant."""

    DONTKNOW = "I am sorry; I am not programmed to respond to that."
    CONFIRMATION = "Done."


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
            enum_type=DeviceName, task_desc="which device is the resident referring to"
        )

    def can_perform(self, state: StructuredIntent, io: IOContainer) -> bool:
        return bool(
            state.intent in (ResidentIntent.TURN_OFF, ResidentIntent.TURN_ON, ResidentIntent.LOCK, ResidentIntent.UNLOCK)
            and not state.object
        )

    def perform(self, state: StructuredIntent, io: IOContainer) -> None:
        utterance = cast(Utterance, io.a.utterance)
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
        mode = self._mode_interpreter(utterance.phrase, llm_model, num_trials=1)[0]
        state.object = mode if mode else KState.UNKNOWN
        print(
            f"--> [Process intent decision process] -> recognized mode as {state.object}"
        )


class ExtractIntentDeviceQuery(Operator[StructuredIntent]):
    """
    Super-process operator: ProcessHumanIntent
    INIT: Instantiate an EnumClassifer for Device
    WHEN: Intent is ResidentIntent.GET_DEVICE_INFO and Object is None
    THEN: Interpret user utterance as a DeviceQuery, KState.UNKNOWN if failed
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._interpreter = ModelPopulator(
            DeviceQuery,
            task_desc="help the resident understand the state of devices in their rooms",
        )

    def can_perform(self, state: StructuredIntent, io: IOContainer) -> bool:
        return bool(
            state.intent is (ResidentIntent.GET_DEVICE_INFO) and not state.object
        )

    def perform(self, state: StructuredIntent, io: IOContainer) -> None:
        utterance = cast(Utterance, io.a.utterance)
        query = self._interpreter(utterance.phrase, llm_model)
        state.object = query if query else KState.UNKNOWN
        print(
            f"--> [Process intent decision process] -> recognized query {state.object}"
        )


def is_process_human_intent_terminal(state: StructuredIntent, _io: IOContainer) -> bool:
    """Super-process operator: ProcessHumanIntent
    terminate decision process when both intent and object have been classified"""
    return state.intent is not None and state.object is not None


class ProcessHumanIntent(Operator[HomeState]):
    """
    INIT: Instantiate DecisionProcess for language interpretation.
    WHEN: Raw utterance exists but structured human intent is not populated.
    THEN: Invoke child DecisionProcess to extract a fully resolved StructuredIntent.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._human_utterance: Utterance | None = None
        self._dp: DecisionProcess[StructuredIntent] = DecisionProcess(StructuredIntent)
        self._dp.add_operator(ExtractIntent("extract_intent_class"))
        self._dp.add_operator(ExtractIntentDevice("extract_intent_device"))
        self._dp.add_operator(ExtractIntentMode("extract_intent_mode"))
        self._dp.add_operator(ExtractIntentDeviceQuery("extract_intent_device_query"))
        self._dp.add_termination_check(is_process_human_intent_terminal)

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        self._human_utterance = cast(Utterance, io.i.interaction)
        return bool(self._human_utterance.phrase and not state.human_intent)

    def perform(self, state: HomeState, io: IOContainer) -> None:
        print("--> [Interpret Intent triggered]")
        self._dp.reinit()
        state.human_intent = self._dp(utterance=self._human_utterance)
        state.human_utterance = self._human_utterance
        print(f"--> [Interpreted Intent] human expressed: {state.human_intent}")


class UpdateWorldModel(Operator[HomeState]):
    """WHEN: there are sensor values that are different from the internal world model
    THEN: update the world graph to new values"""

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._to_update: dict[str, Any] = {}

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        observation = cast(Observation, io.i.devices)
        for device_name, raw_state in observation.model_dump().items():
            mydevice: Device = cast(
                Device, state.world.get_entity(device_name, linked=False)
            )
            if mydevice.dstate != raw_state:
                self._to_update[device_name] = raw_state
        return len(self._to_update) > 0

    def perform(self, state: HomeState, io: IOContainer) -> None:
        for device_name, raw_state in self._to_update.items():
            mydevice = state.world.get_entity(device_name)
            print(
                f"--> [Update internal world model] -> setting {mydevice.e.name}"
                f" to {DeviceState(raw_state)}"
            )
            mydevice.e.dstate = DeviceState(raw_state)
            mydevice.update()
            # io.o.interaction(Utterance(phrase=f"Setting {mydevice.e.name} to {raw_state}"))
        self._to_update.clear()


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


class GenerateDeviceQueryResponse(Operator[HomeState]):
    """
    WHEN: human intent has been parsed as a device query
    THEN: execute the device query against the world graph and generate an NL response
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent:
            return (
                state.human_intent.intent is ResidentIntent.GET_DEVICE_INFO
                and state.human_intent.object is not None
            )
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        query = cast(DeviceQuery, state.human_intent.object)
        print("--> [Generate response to device query triggered]")
        facts = state.world.snapshot.by(
            In,
            lambda in1: (
                isinstance(in1.entity1, Device)
                and (query.dtype in in1.entity1.dtype if query.dtype else True)
                and (
                    query.dstate is in1.entity1.dstate
                    if query.dstate
                    else True and in1.entity2.name == query.room
                )
            ),
        )
        # fact_list = [fact for fact in facts]
        fact_list = list(facts)
        print(f"--> [Found relevant facts] --> {fact_list}")
        response = describe_facts(
            instances=fact_list,
            task_desc=f"""resident question: {state.human_utterance}. Generate a short answer
            to this question using the facts""",
            llm=llm_model,
        )
        io.o.interaction(Utterance(phrase=response))
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
        self._device: Device
        self._signal: ControlSignal

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent and isinstance(state.human_intent.object, DeviceName):
            self._device = cast(
                Device, state.world.get_entity(state.human_intent.object, linked=False)
            )
            if DeviceType.LIGHTABLE in self._device.dtype:
                if state.human_intent.intent is ResidentIntent.TURN_ON:
                    self._signal = ControlSignal.TURN_ON
                elif state.human_intent.intent is ResidentIntent.TURN_OFF:
                    self._signal = ControlSignal.TURN_OFF
                return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(
            Action(device=cast(DeviceName, self._device.name), signal=self._signal)
        )
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
        self._device: Device
        self._signal: ControlSignal

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent and isinstance(state.human_intent.object, DeviceName):
            self._device = cast(
                Device, state.world.get_entity(state.human_intent.object, linked=False)
            )
            if DeviceType.RUNNABLE in self._device.dtype:
                if state.human_intent.intent is ResidentIntent.TURN_ON:
                    self._signal = ControlSignal.START
                elif state.human_intent.intent is ResidentIntent.TURN_OFF:
                    self._signal = ControlSignal.STOP
                return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(
            Action(device=cast(DeviceName, self._device.name), signal=self._signal)
        )
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
        self._device: Device
        self._signal: ControlSignal

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        if state.human_intent and isinstance(state.human_intent.object, DeviceName):
            self._device = cast(
                Device, state.world.get_entity(state.human_intent.object, linked=False)
            )
            if DeviceType.LOCKABLE in self._device.dtype:
                if state.human_intent.intent is ResidentIntent.LOCK:
                    self._signal = ControlSignal.LOCK
                elif state.human_intent.intent is ResidentIntent.UNLOCK:
                    self._signal = ControlSignal.UNLOCK
                return True
        return False

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(
            Action(device=cast(DeviceName, self._device.name), signal=self._signal)
        )
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
        self._mode: Mode

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


def main() -> None:
    """main method"""
    state: HomeState = HomeState(mode=Mode.DAY)
    dp = DecisionProcess[HomeState](lambda: state)

    assistant: Cogent[DecisionProcess[HomeState]] = Cogent(decision_process=dp)

    devices = SmartHomeDevices()
    interaction = HumanInteraction()
    assistant.add_sensor(devices).add_actuator(devices)
    assistant.add_sensor(interaction).add_actuator(interaction)
    assistant.dp.add_operator(UpdateWorldModel("update_world_model"))
    assistant.dp.add_operator(ProcessHumanIntent("process_human_input"))
    assistant.dp.add_operator(
        GenerateDeviceQueryResponse("generate_device_query_response", terminal=True)
    )
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
