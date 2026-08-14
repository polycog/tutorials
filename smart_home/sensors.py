from .devices import Appliance, Basket, Light, Lock


class LampSensor:
    """Read-only sensor reporting the current state of a light."""

    def __init__(self, light: Light):
        self._light = light

    def read(self) -> str:
        return "on" if self._light.is_on else "off"


class LockSensor:
    """Read-only sensor reporting whether a lock is engaged."""

    def __init__(self, lock: Lock):
        self._lock = lock

    def read(self) -> str:
        return "locked" if self._lock.is_locked else "unlocked"


class ApplianceSensor:
    """Read-only sensor reporting whether an appliance is running."""

    def __init__(self, appliance: Appliance):
        self._appliance = appliance

    def read(self) -> str:
        return "running" if self._appliance.is_running else "idle"


class BasketSensor:
    """Read-only sensor reporting whether a basket is full."""

    def __init__(self, basket: Basket):
        self._basket = basket

    def read(self) -> str:
        return "full" if self._basket.is_full else "empty"
