## All necessary imports
from dataclasses import dataclass
from enum import Enum, auto

from cognition import DecisionProcess, IOContainer, Operator


class Mode(Enum):
    """enum to maintain the mode home assistant is operating in"""

    DAY = auto()
    EVENING = auto()
    MIDNIGHT = auto()


class Lamp(Enum):
    """enum to capture lamp state"""

    ON = auto()
    OFF = auto()


class Switch(Enum):
    """enum to capture switch state"""

    ENABLED = auto()
    DISABLED = auto()


@dataclass
class HomeState:
    """describe the current state"""

    mode: Mode
    switch: Switch
    actuated: bool = False

    @property
    def lamp(self) -> Lamp:
        """automatically set the lamp state"""
        if self.switch is Switch.ENABLED:
            return Lamp.ON
        return Lamp.OFF


class TurnLightOff(Operator[HomeState]):  # type: ignore[no-redef]
    """
    when: it is MIDNIGHT mode and the lamp is ON.
    then: disable the switch (and turn-off the lamp), and set the actuated flag.
    """

    def can_perform(self, state: HomeState, _io: IOContainer) -> bool:
        """propose when it is MIDNIGHT mode and the lamp is ON"""
        return state.mode is Mode.MIDNIGHT

    def perform(self, state: HomeState, _io: IOContainer) -> None:
        """apply to disable the switch (and turn-off the lamp), and set the actuated flag."""
        if state.lamp is Lamp.ON:
            state.switch = Switch.DISABLED
        state.actuated = True


class TurnLightOn(Operator[HomeState]):
    """Transition: keep light on."""

    def can_perform(self, state: HomeState, _io: IOContainer) -> bool:
        """propose when it's night mode and the lamp is physically on."""
        return state.mode is Mode.EVENING

    def perform(self, state: HomeState, _io: IOContainer) -> None:
        """apply to flip the actuator switch off (lamp off) and set the actuated flag"""
        if state.lamp is Lamp.OFF:
            state.switch = Switch.ENABLED
        state.actuated = True


def is_terminal(state: HomeState, _io: IOContainer) -> bool:
    """
    Evaluates if the current decision cycle has reached a terminal step.

    Returns True if an operator successfully flagged 'actuated', indicating
    a state mutation or external action command has been processed.
    """
    actuated = state.actuated
    state.actuated = False
    return actuated


# 1. Initialize state in MIDNIGHT mode with lamp turn on and switch enabled.
state: HomeState = HomeState(mode=Mode.MIDNIGHT, switch=Switch.ENABLED)

# 2. Instantiate the decision process, passing a lambda that resolves to your state.
dp: DecisionProcess[HomeState] = DecisionProcess(lambda: state)

# 3. Register your operator and give it a readable name
dp.add_operator(TurnLightOff("turn_light_off"))
dp.add_operator(TurnLightOn("turn_light_on"))

# 4. Register the termination check method
dp.add_termination_check(is_terminal)

# 5. Test execution flow.
print(f"Before decision process runs: {state.lamp=}, {state.switch=}")
dp.run_until_done()
print(f"After decision process runs: {state.lamp=}, {state.switch=}")
