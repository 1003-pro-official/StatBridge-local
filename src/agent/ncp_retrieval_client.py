from __future__ import annotations

import os
import time
import uuid
import copy
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import requests

from ncp_clova_client import _load_env


_load_env()


@dataclass(slots=True)
class RetrievalSettings:
    api_key: str = (
        os.getenv("NCP_CLOVA_API_KEY", "").strip()
        or os.getenv("NCP_API_KEY", "").strip()
        or os.getenv("CLOVA_STUDIO_API_KEY", "").strip()
    )
    base_url: str = os.getenv("NCP_CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com").rstrip("/")
    embedding_url: str = os.getenv("NCP_EMBEDDING_URL", "").strip()
    reranker_url: str = os.getenv("NCP_RERANKER_URL", "").strip()
    timeout: int = int(os.getenv("NCP_RETRIEVAL_TIMEOUT", os.getenv("NCP_TIMEOUT", "60")))


class NcpRetrievalError(RuntimeError):
    pass


class NcpRetrievalClient:
    """Official CLOVA Studio Embedding v2 and Reranker client."""

    def __init__(self, settings: RetrievalSettings | None = None, session: requests.Session | None = None) -> None:
        self.settings = settings or RetrievalSettings()
        self.session = session or requests.Session()
        self._embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._rerank_cache: OrderedDict[tuple[str, tuple[str, ...]], dict[str, float]] = OrderedDict()

    @property
    def configured(self) -> bool:
        return bool(self.settings.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.settings.api_key:
            raise NcpRetrievalError("NCP API key is not configured")
        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        response = None
        for attempt in range(8):
            try:
                response = self.session.post(url, headers=self._headers(), json=body, timeout=self.settings.timeout)
            except requests.RequestException as exc:
                if attempt == 7:
                    raise NcpRetrievalError(f"NCP retrieval request failed: {exc}") from exc
                time.sleep(min(30, 2 ** attempt))
                continue
            if response.status_code != 429:
                break
            retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
            try:
                wait = float(retry_after) if retry_after else min(60, 5 * (attempt + 1))
            except ValueError:
                wait = min(60, 5 * (attempt + 1))
            time.sleep(max(1.0, wait))
        assert response is not None
        if response.status_code >= 400:
            raise NcpRetrievalError(f"NCP retrieval HTTP {response.status_code}: {response.text[:800]}")
        try:
            return response.json()
        except ValueError as exc:
            raise NcpRetrievalError("NCP retrieval returned invalid JSON") from exc

    def embed(self, text: str) -> list[float]:
        cache_key=str(text)[:8192]
        if cache_key in self._embedding_cache:
            self._embedding_cache.move_to_end(cache_key)
            return list(self._embedding_cache[cache_key])
        url = self.settings.embedding_url or f"{self.settings.base_url}/v1/api-tools/embedding/v2/"
        payload = self._post(url, {"text": cache_key})
        vector = (payload.get("result") or {}).get("embedding")
        if not isinstance(vector, list) or not vector:
            raise NcpRetrievalError("Embedding v2 response did not contain result.embedding")
        result=[float(value) for value in vector]
        self._embedding_cache[cache_key]=result
        if len(self._embedding_cache)>256:
            self._embedding_cache.popitem(last=False)
        return list(result)

    def rerank(self, query: str, documents: list[dict[str, str]]) -> dict[str, float]:
        if not documents:
            return {}
        cache_key=(str(query),tuple(str(document.get("id")) for document in documents))
        if cache_key in self._rerank_cache:
            self._rerank_cache.move_to_end(cache_key)
            return dict(self._rerank_cache[cache_key])
        url = self.settings.reranker_url or f"{self.settings.base_url}/v1/api-tools/reranker"
        payload = self._post(url, {"query": query, "documents": documents, "maxTokens": 1024})
        cited = (payload.get("result") or {}).get("citedDocuments") or []
        total = max(1, len(cited))
        result={
            str(doc.get("id")): round(1.0 - (index / total), 6)
            for index, doc in enumerate(cited)
            if doc.get("id") is not None
        }
        self._rerank_cache[cache_key]=copy.deepcopy(result)
        if len(self._rerank_cache)>256:
            self._rerank_cache.popitem(last=False)
        return result
