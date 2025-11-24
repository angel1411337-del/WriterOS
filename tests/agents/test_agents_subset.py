import os
import sys
import types
from typing import Any

import pytest


class _FakeLogger:
    def __init__(self, name="test"):
        self.name = name
        self.messages = []

    def bind(self, **kwargs):
        self.messages.append(("bind", kwargs))
        return self

    def info(self, *args, **kwargs):
        self.messages.append(("info", args, kwargs))

    def warning(self, *args, **kwargs):
        self.messages.append(("warning", args, kwargs))

    def error(self, *args, **kwargs):
        self.messages.append(("error", args, kwargs))


# Ensure API key is present before project modules import environment-dependent singletons
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Patch structlog dependency before importing project modules
fake_structlog = types.SimpleNamespace(
    get_logger=lambda name=None: _FakeLogger(name), configure=lambda **kwargs: None
)
sys.modules.setdefault("structlog", fake_structlog)

from writeros.agents import base, chronologist, mechanic, navigator, stylist


class FakeChain:
    def __init__(self, result: Any):
        self.result = result
        self.contexts = []

    def __or__(self, other: Any):
        # Support chaining with any object (LLM, parser, etc.)
        return self

    async def ainvoke(self, context: dict):
        self.contexts.append(context)
        return self.result


class FakeLLM:
    def __init__(self, structured_result: Any = None, invocation_result: Any = None):
        self.structured_result = structured_result or {}
        self.invocation_result = invocation_result or "ok"
        self.received_schema = None

    def with_structured_output(self, schema):
        self.received_schema = schema
        return FakeChain(self.structured_result)

    def __or__(self, other: Any):
        return FakeChain(self.invocation_result)


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def fake_prompt(monkeypatch):
    def _make_prompt(result):
        def from_messages(_):
            return FakeChain(result)

        for module in (navigator, stylist, mechanic, chronologist):
            monkeypatch.setattr(
                module.ChatPromptTemplate, "from_messages", staticmethod(from_messages)
            )
        return result

    return _make_prompt


@pytest.fixture
def stub_base_init(monkeypatch):
    def _apply(fake_llm=None):
        fake_llm = fake_llm or FakeLLM()

        def init(self, model_name="gpt-5.1"):
            self.model_name = model_name
            self.llm = fake_llm
            self.log = base.logger

        monkeypatch.setattr(base.BaseAgent, "__init__", init)
        return fake_llm

    return _apply


class SampleAgent(base.BaseAgent):
    async def run(self):
        return "ran"


def test_base_agent_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        SampleAgent()


def test_base_agent_initializes_llm(monkeypatch):
    created_args = {}

    class DummyLLM:
        def __init__(self, model, temperature, openai_api_key):
            created_args.update(
                {
                    "model": model,
                    "temperature": temperature,
                    "api_key": openai_api_key,
                }
            )

    monkeypatch.setattr(base, "ChatOpenAI", DummyLLM)
    agent = SampleAgent(model_name="custom-model")

    assert agent.model_name == "custom-model"
    assert created_args == {
        "model": "custom-model",
        "temperature": 0.7,
        "api_key": "test-key",
    }


@pytest.mark.anyio("asyncio")
async def test_base_run_must_be_overridden():
    base_agent = base.BaseAgent.__new__(base.BaseAgent)
    with pytest.raises(NotImplementedError):
        await base_agent.run()


@pytest.mark.anyio("asyncio")
async def test_navigator_run_uses_prompt_and_extractor(fake_prompt, stub_base_init):
    result = {"locations": []}
    fake_prompt(result)
    fake_llm = stub_base_init(FakeLLM(structured_result=result))

    agent = navigator.NavigatorAgent()
    output = await agent.run("text", "notes", "Title")

    assert output == result
    assert fake_llm.received_schema.__name__ == "NavigationSchema"


@pytest.mark.anyio("asyncio")
async def test_stylist_critique_returns_llm_output(fake_prompt, stub_base_init):
    fake_prompt("styled output")
    stub_base_init(FakeLLM(invocation_result="styled output"))

    agent = stylist.StylistAgent()
    feedback = await agent.critique_prose("draft text", "rules")

    assert feedback == "styled output"


@pytest.mark.anyio("asyncio")
async def test_mechanic_run_extracts_systems(fake_prompt, stub_base_init):
    extraction = {"systems": ["alchemy"]}
    fake_prompt(extraction)
    fake_llm = stub_base_init(FakeLLM(structured_result=extraction))

    agent = mechanic.MechanicAgent()
    response = await agent.run("full", "notes", "Title")

    assert response == extraction
    assert fake_llm.received_schema.__name__ == "MechanicExtraction"


@pytest.mark.anyio("asyncio")
async def test_chronologist_run_builds_timeline(fake_prompt, stub_base_init):
    timeline = {"events": [1, 2, 3]}
    fake_prompt(timeline)
    fake_llm = stub_base_init(FakeLLM(structured_result=timeline))

    agent = chronologist.ChronologistAgent()
    result = await agent.run("story", "prior", "Chronology")

    assert result == timeline
    assert fake_llm.received_schema.__name__ == "TimelineExtraction"
