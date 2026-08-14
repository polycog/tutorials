"""Demo smart home agent built with polycog cognition."""

import time
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from typing import cast

from cognition import (
    Actuator,
    Cogent,
    DecisionProcess,
    DecisionProcessErrorMessage,
    IOContainer,
    Operator,
    Sensor,
)

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


class Mode(Enum):
    """Operating modes for the home assistant."""

    DAY = auto()
    EVENING = auto()
    MIDNIGHT = auto()


@dataclass(frozen=True)
class Observation:
    """State observation from the home simulation."""

    lamp: DeviceState


@dataclass(frozen=True)
class Action:
    """Command action to execute on home devices."""

    lamp: ControlSignal


@dataclass
class HomeState:
    """Internal state maintained by the cogent"""

    mode: Mode
    timer_expires_at: float = 0.0


# =============================================================================
# Global Client
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


# =============================================================================
# Sensors & Actuators
# =============================================================================


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


# =============================================================================
# Agent run
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
    """main method"""
    state = HomeState(mode=Mode.MIDNIGHT)
    dp = DecisionProcess[HomeState](lambda: state)
    assistant: Cogent[DecisionProcess[HomeState]] = Cogent(dp)
    devices = SmartHomeDevices()
    assistant.add_sensor(devices).add_actuator(devices)
    assistant.dp.add_operator(TurnLightOff("turn_light_off", terminal=True))
    assistant.dp.add_operator(StartTimer("start_timer"))
    assistant.dp.add_operator(ResetTimer("reset_timer"))
    run_cogent(assistant)


if __name__ == "__main__":
    main()
