"""utility functions for tutorial"""
import time
from typing import Any

from cognition import Cogent, DecisionProcess, DecisionProcessErrorMessage


def run_cogent(cogent: Cogent[DecisionProcess[Any]]) -> None:
    """Run the cogent's perpetual Perceive-Decide-Act loop."""

    def gate_no_potential_actions(
        err: DecisionProcessErrorMessage, _cogent: Cogent[DecisionProcess[Any]]
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
        # cogent(run_forever, dp_err_p=gate_no_potential_actions)
        cogent(cogent.gate_run_forever, dp_err_p=gate_no_potential_actions)
    except KeyboardInterrupt:
        print("\nExecution interrupted.")
