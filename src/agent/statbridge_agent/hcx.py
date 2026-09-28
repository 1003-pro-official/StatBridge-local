from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://clovastudio.stream.ntruss.com/v1/openai"


@dataclass(frozen=True)
class HCXConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = "HCX-007"
    timeout: int = 90

    @classmethod
    def from_env(cls) -> HCXConfig:
        # .env 는 NCP_API_KEY, 선택적 재정의는 HCX_* 를 쓴다.
        return cls(
            api_key=os.getenv("HCX_API_KEY") or os.getenv("NCP_API_KEY", ""),
            base_url=os.getenv("HCX_BASE_URL", DEFAULT_BASE_URL),
            model=os.getenv("HCX_MODEL", "HCX-007"),
        )


def build_payload(model: str, prompt: str, *, schema: dict | None) -> dict:
    payload: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if schema is not None:
        # HCX-007 Structured Outputs는 추론(reasoning)과 동시 사용 불가 →
        # response_format을 쓰려면 reasoning_effort=none 이 필수다.
        payload["reasoning_effort"] = "none"
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "statbridge_intent", "schema": schema},
        }
    return payload


def parse_response(raw: dict) -> str:
    return raw["choices"][0]["message"]["content"]


class HCXGenerator:
    def __init__(self, config: HCXConfig):
        self._config = config

    def generate(self, prompt: str, *, schema: dict | None = None) -> str | dict:
        if not self._config.api_key:
            raise RuntimeError("HCX_API_KEY 또는 NCP_API_KEY가 설정되지 않았습니다.")
        payload = build_payload(self._config.model, prompt, schema=schema)
        req = Request(
            f"{self._config.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(req, timeout=self._config.timeout) as resp:
            content = parse_response(json.loads(resp.read()))
        return json.loads(content) if schema is not None else content
