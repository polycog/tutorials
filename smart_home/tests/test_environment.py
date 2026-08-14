import pytest

from smart_home import SmartHomeEnvironment


def test_simple_mode_has_one_light():
    env = SmartHomeEnvironment(mode="simple")
    assert env.devices == {"lamp": "light"}
    assert env.observe() == {"lamp": "off"}


def test_realistic_mode_has_lights_a_lock_appliances_and_a_basket():
    env = SmartHomeEnvironment(mode="realistic")
    assert env.devices == {
        "bedroom": "light",
        "living_room": "light",
        "kitchen": "light",
        "bathroom": "light",
        "main_door": "lock",
        "dishwasher": "appliance",
        "washer": "appliance",
        "dryer": "appliance",
        "laundry_basket": "basket",
    }
    assert env.observe() == {
        "bedroom": "off",
        "living_room": "off",
        "kitchen": "off",
        "bathroom": "off",
        "main_door": "locked",
        "dishwasher": "idle",
        "washer": "idle",
        "dryer": "idle",
        "laundry_basket": "empty",
    }


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        SmartHomeEnvironment(mode="bogus")


def test_actuate_switch_turns_light_on_and_off():
    env = SmartHomeEnvironment(mode="simple")
    obs = env.actuate("lamp", "turn_on")
    assert obs["lamp"] == "on"
    assert env.observe()["lamp"] == "on"

    obs = env.actuate("lamp", "turn_off")
    assert obs["lamp"] == "off"
    assert env.observe()["lamp"] == "off"


def test_actuate_lock_locks_and_unlocks():
    env = SmartHomeEnvironment(mode="realistic")
    obs = env.actuate("main_door", "unlock")
    assert obs["main_door"] == "unlocked"

    obs = env.actuate("main_door", "lock")
    assert obs["main_door"] == "locked"


def test_actuate_dishwasher_starts_and_stops():
    env = SmartHomeEnvironment(mode="realistic")
    obs = env.actuate("dishwasher", "start")
    assert obs["dishwasher"] == "running"

    obs = env.actuate("dishwasher", "stop")
    assert obs["dishwasher"] == "idle"


def test_actuate_washer_and_dryer_are_independent():
    env = SmartHomeEnvironment(mode="realistic")
    env.actuate("washer", "start")
    obs = env.observe()
    assert obs["washer"] == "running"
    assert obs["dryer"] == "idle"


def test_actuate_basket_fills_and_empties():
    env = SmartHomeEnvironment(mode="realistic")
    obs = env.actuate("laundry_basket", "fill")
    assert obs["laundry_basket"] == "full"

    obs = env.actuate("laundry_basket", "empty")
    assert obs["laundry_basket"] == "empty"


def test_actuate_only_affects_its_own_device():
    env = SmartHomeEnvironment(mode="realistic")
    env.actuate("kitchen", "turn_on")
    obs = env.observe()
    assert obs["kitchen"] == "on"
    assert obs["bedroom"] == "off"
    assert obs["main_door"] == "locked"
    assert obs["dishwasher"] == "idle"


def test_invalid_action_for_light_raises():
    env = SmartHomeEnvironment(mode="simple")
    with pytest.raises(ValueError):
        env.actuate("lamp", "lock")


def test_invalid_action_for_lock_raises():
    env = SmartHomeEnvironment(mode="realistic")
    with pytest.raises(ValueError):
        env.actuate("main_door", "turn_on")


def test_invalid_action_for_appliance_raises():
    env = SmartHomeEnvironment(mode="realistic")
    with pytest.raises(ValueError):
        env.actuate("dishwasher", "turn_on")


def test_invalid_action_for_basket_raises():
    env = SmartHomeEnvironment(mode="realistic")
    with pytest.raises(ValueError):
        env.actuate("laundry_basket", "start")


def test_unknown_device_raises():
    env = SmartHomeEnvironment(mode="simple")
    with pytest.raises(ValueError):
        env.actuate("bogus", "turn_on")
