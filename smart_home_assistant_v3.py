"""Demo smart home agent built with polycog cognition."""

import os
import time
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, cast

from cognition import (
    Actuator,
    AutoDocEnum,
    Cogent,
    DecisionProcess,
    DecisionProcessErrorMessage,
    DocEnum,
    IOContainer,
    Operator,
    Sensor,
)
from cognition.language import EnumClassifier  ## changed in cognition
from pydantic_ai.models import infer_model

from smart_home.client import SmartHomeClient

# =============================================================================
# Enums & Data Models
# =============================================================================


class DeviceState(StrEnum):
    """Smart home device operational states."""

    ON = "on"
    OFF = "off"


class ControlSignal(StrEnum):
    """Control commands sent to smart home devices."""

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"


class ResidentIntent(AutoDocEnum):
    """Supported resident intent classifications."""

    TURN_OFF_LAMP = "user is asking the assistant to turn the lamp off"
    TURN_ON_LAMP = "user is asking the assistant to turn the lamp on"
    SET_MODE = "user is asking the assistant to set a mode"


class MyIntent(StrEnum):
    """Responses from the assistant to the user"""

    UNKNOWN = "I am sorry; I am not programmed to respond to that."
    CONFIRMATION = "Done."
    GREETING = "Hi!"
    GRATITUDE_ACK = "You are welcome."


class Mode(DocEnum):
    """Operating modes for the home assistant."""

    DAY = auto(), "day mode of smart assistant"
    EVENING = auto(), "evening mode of smart assistant"
    MIDNIGHT = auto(), "midnight mode of smart assistant"


@dataclass(frozen=True)
class Observation:
    """State observation from the home simulation."""

    lamp: DeviceState


@dataclass(frozen=True)
class Action:
    """Command action to execute on home devices."""

    lamp: ControlSignal


@dataclass(frozen=True)
class Utterance:
    """Natural language message phrase."""

    phrase: str | None


@dataclass
class HomeState:
    """Internal state maintained by the cogent"""

    mode: Mode
    timer_expires_at: float = 0.0

    # Language processing
    human_utterance: Utterance | None = None
    human_intent: ResidentIntent | None = None


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
    """Sensor and actuator interface for physical home devices."""

    @property
    def name(self) -> str:
        return "devices"

    def sense(self) -> Observation:
        """Fetch current states of smart home devices."""
        response = client.observe()
        return Observation(lamp=response["lamp"])

    def actuate(self, param: Action) -> None:
        """Execute device commands in the simulation."""
        client.actuate("lamp", param.lamp)


# =============================================================================
# Operators
# =============================================================================


class StartTimer(Operator[HomeState]):
    """
    WHEN: Lamp is ON in MIDNIGHT mode and timer is not set.
    THEN: Start a 5-second countdown timer.
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        """Check if mode is MIDNIGHT, lamp is ON, and no timer is running."""
        observation = cast(Observation, io.i.devices)
        return (
            state.mode is Mode.MIDNIGHT
            and DeviceState(observation.lamp) == DeviceState.ON
            and state.timer_expires_at == 0.0
        )

    def perform(self, state: HomeState, io: IOContainer) -> None:
        """Start a 5-second timer."""
        state.timer_expires_at = time.monotonic() + 5.0
        print("--> [Timer Started] 5-second countdown initialized.")


class TurnLightOff(Operator[HomeState]):
    """
    WHEN: Lamp is ON in MIDNIGHT mode and active timer has expired.
    THEN: Turn off the lamp and reset the timer state.
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        """Check if mode is MIDNIGHT, lamp is ON, and timer has expired."""
        observation = cast(Observation, io.i.devices)
        return (
            state.mode is Mode.MIDNIGHT
            and DeviceState(observation.lamp) == DeviceState.ON
            and state.timer_expires_at != 0
            and time.monotonic() >= state.timer_expires_at
        )

    def perform(self, state: HomeState, io: IOContainer) -> None:
        """Turn off the lamp and reset the timer state."""
        io.o.devices(Action(lamp=ControlSignal.TURN_OFF))
        state.timer_expires_at = 0.0
        print("--> [Action Triggered] Timer expired. Turning light off.")


class ResetTimer(Operator[HomeState]):
    """
    WHEN: Lamp is OFF while a timer is active.
    THEN: Reset the timer to zero.
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        """Check if lamp is OFF while a timer is active."""
        observation = cast(Observation, io.i.devices)
        return observation.lamp == DeviceState.OFF and state.timer_expires_at != 0.0

    def perform(self, state: HomeState, io: IOContainer) -> None:
        """Reset the active timer."""
        state.timer_expires_at = 0.0
        print("--> [Internal Action Triggered] Light off, resetting timer.")


class ProcessHumanIntent(Operator[HomeState]):
    """
    WHEN: User sends a message via the interaction sensor.
    THEN: Parse the message into a resident intent classification.
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._human_utterance: Utterance | None = None
        self._interpreter = EnumClassifier(
            enum_type=ResidentIntent,
            task_desc="what is the resident asking the assistant to do",
        )

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        """Check for unhandled user messages on the interaction link."""
        self._human_utterance = cast(Utterance, io.i.interaction)
        return bool(self._human_utterance.phrase and not state.human_intent)

    def perform(self, state: HomeState, io: IOContainer) -> None:
        """Parse user phrase into a resident intent."""
        print("--> [Interpret Intent triggered]")
        state.human_utterance = self._human_utterance
        state.human_intent = self._interpreter(
            state.human_utterance.phrase, llm=llm_model, num_trials=1
        )[0]
        print(f"--> [Interpreted Intent] human expressed {state.human_intent}")
        if state.human_intent is None:
            io.o.interaction(Utterance(phrase=MyIntent.UNKNOWN))


class ActOnHumanIntentTurnOff(Operator[HomeState]):
    """
    WHEN: Resident intent is TURN_OFF_LAMP
    THEN: turn the lamp off
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        return state.human_intent is ResidentIntent.TURN_OFF_LAMP

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(Action(lamp=ControlSignal.TURN_OFF))
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Action Triggered] Reacting to human request. Turning light OFF.")
        state.human_intent = None
        state.human_utterance = None


class ActOnHumanIntentTurnOn(Operator[HomeState]):
    """
    WHEN: Resident intent is TURN_ON_LAMP
    THEN: Turn the lamp off
    """

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        return state.human_intent is ResidentIntent.TURN_ON_LAMP

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.devices(Action(lamp=ControlSignal.TURN_ON))
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Action Triggered] Reacting to human request. Turning light ON.")
        state.human_intent = None
        state.human_utterance = None


class ActOnHumanIntentSetMode(Operator[HomeState]):
    """
    WHEN: Resident intent is to SET_MODE
    THEN: Parse which mode, and set that mode
    """

    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._human_utterance: Utterance | None = None
        self._interpreter = EnumClassifier(
            enum_type=Mode,
            task_desc="which mode is indicated by the user",
        )

    def can_perform(self, state: HomeState, io: IOContainer) -> bool:
        return state.human_intent is ResidentIntent.SET_MODE

    def perform(self, state: HomeState, io: IOContainer) -> None:
        io.o.interaction(Utterance(phrase=MyIntent.CONFIRMATION))
        print("--> [Interpret Mode triggered]")
        mode: Mode | None = self._interpreter(
            state.human_utterance.phrase, llm=llm_model, num_trials=1
        )[0]
        if mode:
            state.mode = mode
            print(f"--> [Internal Action Triggered] Setting mode to {mode}")
        else:
            print(
                f"--> [Internal Action Triggered] invalid {mode} mode detected; not reacting."
            )
        state.human_intent = None


# =============================================================================
# Agent Setup & Main Loop
# =============================================================================


def run_cogent(cogent: Cogent[DecisionProcess[HomeState]]) -> None:
    """Run the cogent's perpetual Perceive-Decide-Act loop."""

    def run_forever(_cogent: Cogent[DecisionProcess[HomeState]]) -> bool:
        """Keep the execution loop running continuously."""
        return True

    def gate_no_potential_actions(
        err: DecisionProcessErrorMessage, _cogent: Cogent[DecisionProcess[HomeState]]
    ) -> bool:
        """
        Handle decision process errors.
        Allows the agent to remain idle when no actions are proposed, while pausing
        briefly to prevent tight CPU looping.
        """
        time.sleep(0.5)
        if err is DecisionProcessErrorMessage.NO_PROPOSAL:
            return True  # Suppress error and continue execution loop
        raise RuntimeError(err)  # Re-raise unexpected critical errors

    print(
        "Cogent running. Click 'Interrupt Kernel' in Jupyter or press Ctrl+C in terminal to stop.\n"
    )
    try:
        # Pass the loop predicate and error handling policy to the Cogent instance
        cogent(run_forever, dp_err_p=gate_no_potential_actions)
    except KeyboardInterrupt:
        print("\nExecution interrupted.")


def main() -> None:
    """main"""
    state = HomeState(mode=Mode.MIDNIGHT)
    dp = DecisionProcess[HomeState](lambda: state)

    assistant: Cogent[DecisionProcess[HomeState]] = Cogent(decision_process=dp)
    assistant.add_sensor(SmartHomeDevices())
    assistant.add_actuator(SmartHomeDevices())
    assistant.add_sensor(HumanInteraction())
    assistant.add_actuator(HumanInteraction())

    ## autonomous action operators
    assistant.dp.add_operator(TurnLightOff("turn_light_off", terminal=True))  ##
    assistant.dp.add_operator(StartTimer("start_timer"))
    assistant.dp.add_operator(ResetTimer("reset_timer"))

    ## intent-interpretation and intent-driven-action operators
    assistant.dp.add_operator(
        ProcessHumanIntent("interpret_human_response", terminal=True)
    )
    assistant.dp.add_operator(
        ActOnHumanIntentTurnOn("intent_turn_light_on", terminal=True)
    )
    assistant.dp.add_operator(
        ActOnHumanIntentTurnOff("intent_turn_light_off", terminal=True)
    )
    assistant.dp.add_operator(ActOnHumanIntentSetMode("intent_set_mode", terminal=True))

    run_cogent(assistant)


if __name__ == "__main__":
    main()
