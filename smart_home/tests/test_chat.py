from smart_home.chat import ChatTranscript


def test_new_transcript_is_empty():
    chat = ChatTranscript()
    assert chat.messages == []


def test_add_appends_and_returns_the_message():
    chat = ChatTranscript()
    message = chat.add("human", "turn on the kitchen light")
    assert message == {"source": "human", "text": "turn on the kitchen light", "processed": False}
    assert chat.messages == [message]


def test_agent_messages_start_processed():
    chat = ChatTranscript()
    message = chat.add("agent", "sure, turning it on")
    assert message["processed"] is True


def test_human_messages_start_unprocessed():
    chat = ChatTranscript()
    message = chat.add("human", "turn on the kitchen light")
    assert message["processed"] is False


def test_messages_preserves_order_across_sources():
    chat = ChatTranscript()
    chat.add("human", "hi")
    chat.add("agent", "hello, how can I help?")
    chat.add("human", "turn off the bedroom light")
    assert chat.messages == [
        {"source": "human", "text": "hi", "processed": False},
        {"source": "agent", "text": "hello, how can I help?", "processed": True},
        {"source": "human", "text": "turn off the bedroom light", "processed": False},
    ]


def test_messages_is_a_copy():
    chat = ChatTranscript()
    chat.add("human", "hi")
    chat.messages.append({"source": "agent", "text": "sneaky", "processed": True})
    assert chat.messages == [{"source": "human", "text": "hi", "processed": False}]


def test_latest_human_message_is_none_when_theres_never_been_one():
    chat = ChatTranscript()
    assert chat.latest_human_message() is None
    chat.add("agent", "hello?")
    assert chat.latest_human_message() is None


def test_latest_human_message_returns_the_most_recent_one():
    chat = ChatTranscript()
    chat.add("human", "first")
    chat.add("agent", "ok")
    chat.add("human", "second")
    assert chat.latest_human_message()["text"] == "second"


def test_acknowledge_latest_human_message_marks_it_processed():
    chat = ChatTranscript()
    chat.add("human", "turn on the lamp")
    acknowledged = chat.acknowledge_latest_human_message()
    assert acknowledged == {"source": "human", "text": "turn on the lamp", "processed": True}
    assert chat.latest_human_message()["processed"] is True


def test_acknowledge_latest_human_message_is_idempotent():
    chat = ChatTranscript()
    chat.add("human", "turn on the lamp")
    chat.acknowledge_latest_human_message()
    acknowledged_again = chat.acknowledge_latest_human_message()
    assert acknowledged_again["processed"] is True


def test_acknowledge_latest_human_message_with_no_human_message_returns_none():
    chat = ChatTranscript()
    chat.add("agent", "hello?")
    assert chat.acknowledge_latest_human_message() is None


def test_a_new_human_message_is_unprocessed_even_after_the_previous_one_was_acknowledged():
    chat = ChatTranscript()
    chat.add("human", "first")
    chat.acknowledge_latest_human_message()
    chat.add("human", "second")
    assert chat.latest_human_message() == {"source": "human", "text": "second", "processed": False}
