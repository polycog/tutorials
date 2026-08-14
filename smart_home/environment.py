from __future__ import annotations

from typing import Literal

from .devices import Appliance, Basket, Light, Lock, Switch
from .sensors import ApplianceSensor, BasketSensor, LampSensor, LockSensor

Mode = Literal["simple", "realistic"]
Action = Literal["turn_on", "turn_off", "lock", "unlock", "start", "stop", "fill", "empty"]
Observation = dict[str, str]

SIMPLE_LIGHTS = ("lamp",)
REALISTIC_LIGHTS = ("bedroom", "living_room", "kitchen", "bathroom")
REALISTIC_LOCKS = ("main_door",)
REALISTIC_APPLIANCES = ("dishwasher", "washer", "dryer")
REALISTIC_BASKETS = ("laundry_basket",)

# Valid actions per device kind, in (turns-it-on, turns-it-off) order. Shared by every
# frontend and the remote API so they don't each redefine this vocabulary.
KIND_ACTIONS: dict[str, tuple[str, str]] = {
    "light": ("turn_on", "turn_off"),
    "lock": ("lock", "unlock"),
    "appliance": ("start", "stop"),
    "basket": ("fill", "empty"),
}


class SmartHomeEnvironment:
    """A smart home whose devices depend on the simulation mode.

    simple mode: a single room ("lamp") with a light switch.
    realistic mode: bedroom, living_room, kitchen, and bathroom lights; a lock on the
    main_door; a dishwasher in the kitchen; and a washer, dryer, and laundry basket in
    the laundry.

    An agent actuates a named device; each device's sensor reports the resulting state.
    """

    def __init__(self, mode: Mode = "simple"):
        if mode not in ("simple", "realistic"):
            raise ValueError(f"Unknown mode: {mode!r}")
        self.mode = mode
        self._switches: dict[str, Switch] = {}
        self._locks: dict[str, Lock] = {}
        self._appliances: dict[str, Appliance] = {}
        self._baskets: dict[str, Basket] = {}
        self._sensors: dict[str, LampSensor | LockSensor | ApplianceSensor | BasketSensor] = {}

        for name in SIMPLE_LIGHTS if mode == "simple" else REALISTIC_LIGHTS:
            light = Light()
            self._switches[name] = Switch(light)
            self._sensors[name] = LampSensor(light)

        for name in REALISTIC_LOCKS if mode == "realistic" else ():
            lock = Lock()
            self._locks[name] = lock
            self._sensors[name] = LockSensor(lock)

        for name in REALISTIC_APPLIANCES if mode == "realistic" else ():
            appliance = Appliance()
            self._appliances[name] = appliance
            self._sensors[name] = ApplianceSensor(appliance)

        for name in REALISTIC_BASKETS if mode == "realistic" else ():
            basket = Basket()
            self._baskets[name] = basket
            self._sensors[name] = BasketSensor(basket)

    @property
    def devices(self) -> dict[str, Literal["light", "lock", "appliance", "basket"]]:
        """Every device this environment has, and its kind."""
        return {
            **{name: "light" for name in self._switches},
            **{name: "lock" for name in self._locks},
            **{name: "appliance" for name in self._appliances},
            **{name: "basket" for name in self._baskets},
        }

    def actuate(self, device: str, action: Action) -> Observation:
        if device in self._switches:
            switch = self._switches[device]
            if action == "turn_on":
                switch.turn_on()
            elif action == "turn_off":
                switch.turn_off()
            else:
                raise ValueError(f"Unknown action {action!r} for light {device!r}")
        elif device in self._locks:
            lock = self._locks[device]
            if action == "lock":
                lock.lock()
            elif action == "unlock":
                lock.unlock()
            else:
                raise ValueError(f"Unknown action {action!r} for lock {device!r}")
        elif device in self._appliances:
            appliance = self._appliances[device]
            if action == "start":
                appliance.start()
            elif action == "stop":
                appliance.stop()
            else:
                raise ValueError(f"Unknown action {action!r} for appliance {device!r}")
        elif device in self._baskets:
            basket = self._baskets[device]
            if action == "fill":
                basket.fill()
            elif action == "empty":
                basket.empty()
            else:
                raise ValueError(f"Unknown action {action!r} for basket {device!r}")
        else:
            raise ValueError(f"Unknown device: {device!r}")
        return self.observe()

    def observe(self) -> Observation:
        return {device: sensor.read() for device, sensor in self._sensors.items()}
