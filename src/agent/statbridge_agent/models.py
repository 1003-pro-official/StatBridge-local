from typing import Protocol


class TextGenerator(Protocol):
    def generate(self, prompt: str, *, schema: dict | None = None) -> str | dict: ...


class MockGenerator:
    """Deterministic parser response for tests without an LLM key."""

    def __init__(self, responses: dict[str, str | dict]):
        self._responses = responses

    def generate(self, prompt: str, *, schema: dict | None = None) -> str | dict:
        return self._responses[prompt]
