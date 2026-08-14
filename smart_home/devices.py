class Light:
    """A lamp that has no controls of its own — its state is driven by a Switch."""

    def __init__(self):
        self._on = False

    @property
    def is_on(self) -> bool:
        return self._on

    def set_on(self, on: bool) -> None:
        self._on = on


class Switch:
    """A switch wired to exactly one light: its on/off state is mirrored by the light."""

    def __init__(self, light: Light):
        self._light = light
        self._on = False

    @property
    def is_on(self) -> bool:
        return self._on

    def turn_on(self) -> None:
        self._on = True
        self._light.set_on(True)

    def turn_off(self) -> None:
        self._on = False
        self._light.set_on(False)


class Lock:
    """A lock on a door. Starts locked, like a real front door would be by default."""

    def __init__(self):
        self._locked = True

    @property
    def is_locked(self) -> bool:
        return self._locked

    def lock(self) -> None:
        self._locked = True

    def unlock(self) -> None:
        self._locked = False


class Appliance:
    """An appliance like a dishwasher, washer, or dryer. Starts idle."""

    def __init__(self):
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False


class Basket:
    """A laundry basket. Starts empty, like one that was just emptied would be."""

    def __init__(self):
        self._full = False

    @property
    def is_full(self) -> bool:
        return self._full

    def fill(self) -> None:
        self._full = True

    def empty(self) -> None:
        self._full = False
