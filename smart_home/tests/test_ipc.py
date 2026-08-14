import asyncio

import requests

from smart_home.smart_home import SmartHome


async def get(url: str):
    return await asyncio.to_thread(requests.get, url)


async def post(url: str, json: dict):
    return await asyncio.to_thread(requests.post, url, json=json)


def test_remote_agent_actuates_running_environment_simple_mode(free_port):
    async def scenario():
        app = SmartHome(mode="simple", port=free_port)
        async with app.run_test() as pilot:
            await pilot.pause()

            base_url = f"http://127.0.0.1:{free_port}"

            response = await get(f"{base_url}/observation")
            assert response.json() == {"lamp": "off"}

            response = await post(f"{base_url}/actuate", {"device": "lamp", "action": "turn_on"})
            assert response.json() == {"lamp": "on"}

            await pilot.pause()
            assert app.env.observe() == {"lamp": "on"}
            assert app.query_one("#switch-lamp").value is True

            response = await post(f"{base_url}/actuate", {"device": "lamp", "action": "turn_off"})
            assert response.json() == {"lamp": "off"}

            response = await post(f"{base_url}/actuate", {"device": "lamp", "action": "bogus"})
            assert response.status_code == 400

            response = await post(f"{base_url}/actuate", {"device": "bogus", "action": "turn_on"})
            assert response.status_code == 400

    asyncio.run(scenario())


def test_remote_agent_actuates_running_environment_realistic_mode(free_port):
    async def scenario():
        app = SmartHome(mode="realistic", port=free_port)
        async with app.run_test() as pilot:
            await pilot.pause()

            base_url = f"http://127.0.0.1:{free_port}"

            response = await get(f"{base_url}/observation")
            assert response.json() == {
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

            response = await post(f"{base_url}/actuate", {"device": "kitchen", "action": "turn_on"})
            assert response.json()["kitchen"] == "on"
            assert response.json()["bedroom"] == "off"

            response = await post(f"{base_url}/actuate", {"device": "main_door", "action": "unlock"})
            assert response.json()["main_door"] == "unlocked"

            response = await post(f"{base_url}/actuate", {"device": "dishwasher", "action": "start"})
            assert response.json()["dishwasher"] == "running"
            assert response.json()["washer"] == "idle"

            response = await post(f"{base_url}/actuate", {"device": "laundry_basket", "action": "fill"})
            assert response.json()["laundry_basket"] == "full"

            await pilot.pause()
            assert app.query_one("#switch-kitchen").value is True
            assert app.query_one("#switch-main_door").value is False
            assert app.query_one("#switch-dishwasher").value is True
            assert app.query_one("#switch-laundry_basket").value is True

            # an action doesn't apply across device kinds
            response = await post(f"{base_url}/actuate", {"device": "main_door", "action": "turn_on"})
            assert response.status_code == 400

            response = await post(f"{base_url}/actuate", {"device": "kitchen", "action": "lock"})
            assert response.status_code == 400

            response = await post(f"{base_url}/actuate", {"device": "washer", "action": "turn_on"})
            assert response.status_code == 400

    asyncio.run(scenario())


def test_remote_agent_chats_with_the_human_at_the_tui(free_port):
    async def scenario():
        app = SmartHome(mode="simple", port=free_port)
        async with app.run_test() as pilot:
            await pilot.pause()

            base_url = f"http://127.0.0.1:{free_port}"

            response = await get(f"{base_url}/chat")
            assert response.json() == []

            app.send_human_message("turn on the lamp")
            await pilot.pause()
            assert app.chat.messages == [
                {"source": "human", "text": "turn on the lamp", "processed": False}
            ]

            response = await get(f"{base_url}/chat")
            assert response.json() == [{"source": "human", "text": "turn on the lamp", "processed": False}]

            response = await post(f"{base_url}/chat", {"message": "sure, turning it on"})
            assert response.json() == {"source": "agent", "text": "sure, turning it on", "processed": True}

            await pilot.pause()
            assert app.chat.messages == [
                {"source": "human", "text": "turn on the lamp", "processed": False},
                {"source": "agent", "text": "sure, turning it on", "processed": True},
            ]

            response = await post(f"{base_url}/chat", {"message": "   "})
            assert response.status_code == 400

            response = await post(f"{base_url}/chat", {})
            assert response.status_code == 400

    asyncio.run(scenario())


def test_remote_agent_acknowledges_the_latest_human_message(free_port):
    async def scenario():
        app = SmartHome(mode="simple", port=free_port)
        async with app.run_test() as pilot:
            await pilot.pause()

            base_url = f"http://127.0.0.1:{free_port}"

            # Nothing to acknowledge yet.
            response = await post(f"{base_url}/chat/ack", {})
            assert response.json() is None

            app.send_human_message("turn on the lamp")
            await pilot.pause()

            response = await post(f"{base_url}/chat/ack", {})
            assert response.json() == {"source": "human", "text": "turn on the lamp", "processed": True}

            # Once acknowledged, it stays acknowledged — reading doesn't undo it, and
            # re-acknowledging is a no-op that returns the same message.
            response = await get(f"{base_url}/chat")
            assert response.json() == [{"source": "human", "text": "turn on the lamp", "processed": True}]

            response = await post(f"{base_url}/chat/ack", {})
            assert response.json() == {"source": "human", "text": "turn on the lamp", "processed": True}

            # A new human message resets the state: it starts unprocessed again.
            app.send_human_message("now turn it off")
            await pilot.pause()
            response = await get(f"{base_url}/chat")
            assert response.json() == [
                {"source": "human", "text": "turn on the lamp", "processed": True},
                {"source": "human", "text": "now turn it off", "processed": False},
            ]

    asyncio.run(scenario())


def test_chat_input_submission_sends_a_human_message(free_port):
    async def scenario():
        app = SmartHome(mode="simple", port=free_port)
        async with app.run_test() as pilot:
            await pilot.pause()

            chat_input = app.query_one("#chat-input")
            chat_input.focus()
            for char in "hello there":
                await pilot.press(char)
            await pilot.press("enter")

            assert app.chat.messages == [{"source": "human", "text": "hello there", "processed": False}]
            assert chat_input.value == ""

    asyncio.run(scenario())


def test_second_server_on_same_port_disables_gracefully(free_port):
    async def scenario():
        app1 = SmartHome(port=free_port)
        async with app1.run_test() as pilot1:
            await pilot1.pause()
            assert app1._server is not None

            app2 = SmartHome(port=free_port)
            async with app2.run_test() as pilot2:
                await pilot2.pause()
                assert app2._server is None

    asyncio.run(scenario())
