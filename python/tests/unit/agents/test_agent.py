# Copyright (c) Microsoft. All rights reserved.

import uuid
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest

from semantic_kernel.agents import Agent
from semantic_kernel.agents.channels.agent_channel import AgentChannel
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.history_reducer.chat_history_reducer import ChatHistoryReducer
from semantic_kernel.contents.history_reducer.chat_history_truncation_reducer import ChatHistoryTruncationReducer
from semantic_kernel.functions.kernel_arguments import KernelArguments


class MockChatHistory:
    """Minimal mock for ChatHistory to hold messages."""

    def __init__(self, messages=None):
        self.messages = messages if messages is not None else []


class MockChannel(AgentChannel):
    """Mock channel for testing get_channel_keys and create_channel."""


class MockAgent(Agent):
    """A mock agent for testing purposes."""

    channel_type: ClassVar[type[AgentChannel]] = MockChannel

    def __init__(self, name: str = "Test-Agent", description: str = "A test agent", id: str = None):
        args = {
            "name": name,
            "description": description,
        }
        if id is not None:
            args["id"] = id
        super().__init__(**args)

    async def create_channel(self) -> AgentChannel:
        return AsyncMock(spec=AgentChannel)


async def test_agent_initialization():
    name = "TestAgent"
    description = "A test agent"
    id_value = str(uuid.uuid4())

    agent = MockAgent(name=name, description=description, id=id_value)

    assert agent.name == name
    assert agent.description == description
    assert agent.id == id_value


async def test_agent_default_id():
    agent = MockAgent()

    assert agent.id is not None
    assert isinstance(uuid.UUID(agent.id), uuid.UUID)


def test_get_channel_keys():
    agent = MockAgent()
    keys = agent.get_channel_keys()

    assert len(list(keys)) == 1, "Should return a single key"


async def test_create_channel():
    agent = MockAgent()
    channel = await agent.create_channel()

    assert isinstance(channel, AgentChannel)


async def test_agent_equality():
    id_value = str(uuid.uuid4())

    agent1 = MockAgent(name="TestAgent", description="A test agent", id=id_value)
    agent2 = MockAgent(name="TestAgent", description="A test agent", id=id_value)

    assert agent1 == agent2

    agent3 = MockAgent(name="TestAgent", description="A different description", id=id_value)
    assert agent1 != agent3

    agent4 = MockAgent(name="AnotherAgent", description="A test agent", id=id_value)
    assert agent1 != agent4


async def test_agent_equality_different_type():
    agent = MockAgent(name="TestAgent", description="A test agent", id=str(uuid.uuid4()))
    non_agent = "Not an agent"

    assert agent != non_agent


async def test_agent_hash():
    id_value = str(uuid.uuid4())

    agent1 = MockAgent(name="TestAgent", description="A test agent", id=id_value)
    agent2 = MockAgent(name="TestAgent", description="A test agent", id=id_value)

    assert hash(agent1) == hash(agent2)

    agent3 = MockAgent(name="TestAgent", description="A different description", id=id_value)
    assert hash(agent1) != hash(agent3)


async def test_reduce_history_no_reducer():
    agent = Agent()
    history = MockChatHistory(messages=["msg1", "msg2"])

    result = await agent.reduce_history(history)

    assert result is False, "reduce_history should return False if no history_reducer is set"
    assert history.messages == ["msg1", "msg2"], "History should remain unchanged"


async def test_reduce_history_reducer_returns_none():
    agent = Agent()
    agent.history_reducer = AsyncMock(spec=ChatHistoryReducer)
    agent.history_reducer.reduce = AsyncMock(return_value=None)

    history = MockChatHistory(messages=["original1", "original2"])
    result = await agent.reduce_history(history)

    assert result is False, "reduce_history should return False if reducer returns None"
    assert history.messages == ["original1", "original2"], "History should remain unchanged"


async def test_reduce_history_reducer_returns_messages():
    agent = Agent()
    agent.history_reducer = ChatHistoryTruncationReducer(target_count=1)
    history = MockChatHistory(
        messages=[
            ChatMessageContent(role="user", content="original message"),
            ChatMessageContent(role="assistant", content="assistant message"),
        ]
    )

    result = await agent.reduce_history(history)

    assert result is True, "reduce_history should return True if new messages are returned"
    assert history.messages is not None


def test_get_channel_keys_no_channel_type():
    agent = Agent()
    with pytest.raises(NotImplementedError):
        list(agent.get_channel_keys())


def test_get_channel_keys_with_channel_and_reducer():
    agent = MockAgent()
    reducer = ChatHistoryTruncationReducer(target_count=1)
    agent.history_reducer = reducer

    keys = list(agent.get_channel_keys())
    assert len(keys) == 3, "Should return three keys: channel, reducer class name, and reducer hash"
    assert keys[0] == "MockChannel"
    assert keys[1] == "ChatHistoryTruncationReducer"
    assert keys[2] == str(reducer.__hash__), "Should return the string of the reducer's __hash__"


def test_merge_arguments_both_none():
    agent = Agent()
    merged = agent.merge_arguments(None)
    assert merged is None, "Should return None if both agent.arguments and override_args are None"


def test_merge_arguments_agent_none_override_not_none():
    agent = Agent()
    override = KernelArguments(settings={"key": "override"}, param1="val1")

    merged = agent.merge_arguments(override)
    assert merged is override, "If agent.arguments is None, just return override_args"


def test_merge_arguments_override_none_agent_not_none():
    agent = Agent()
    agent.arguments = KernelArguments(settings={"key": "base"}, param1="baseVal")

    merged = agent.merge_arguments(None)
    assert merged is agent.arguments, "If override_args is None, should return the agent's arguments"


def test_merge_arguments_both_not_none():
    agent = Agent()
    agent.arguments = KernelArguments(settings={"key1": "val1", "common": "base"}, param1="baseVal")
    override = KernelArguments(settings={"key2": "override_val", "common": "override"}, param2="override_param")

    merged = agent.merge_arguments(override)

    assert merged.execution_settings["key1"] == "val1", "Should retain original setting from agent"
    assert merged.execution_settings["key2"] == "override_val", "Should include new setting from override"
    assert merged.execution_settings["common"] == "override", "Override should take precedence"

    assert merged["param1"] == "baseVal", "Should retain base param from agent"
    assert merged["param2"] == "override_param", "Should include param from override"
