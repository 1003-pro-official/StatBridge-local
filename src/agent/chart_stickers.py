"""Local, allow-listed transparent stickers; no arbitrary image URLs or file reads."""
from __future__ import annotations

import base64
import json
import math
from functools import lru_cache
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parent / "frontend" / "public" / "stickers"


@lru_cache(maxsize=1)
def sticker_catalog() -> list[dict]:
    return json.loads((ASSET_ROOT / "catalog.json").read_text(encoding="utf-8"))


def sticker_asset(asset_id: str) -> dict:
    for asset in sticker_catalog():
        if asset["id"] == asset_id:
            return asset
    raise ValueError("이모티콘 목록에 없는 이미지입니다. 목록에서 다시 선택해 주세요.")


@lru_cache(maxsize=512)
def sticker_source(asset_id: str, angle: float) -> str:
    """Embed the PNG in a square SVG with enough room for arbitrary rotation.

    Same square envelope is used by browser preview and Plotly image export.
    This keeps artwork proportions and avoids clipping at diagonal angles.
    """
    asset = sticker_asset(asset_id)
    width, height = asset["width"], asset["height"]
    side = math.ceil(math.hypot(width, height))
    png = base64.b64encode((ASSET_ROOT / asset["file"]).read_bytes()).decode("ascii")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'width="{side}" height="{side}" viewBox="0 0 {side} {side}">'
           f'<image x="{(side-width)/2}" y="{(side-height)/2}" width="{width}" height="{height}" '
           f'transform="rotate({angle} {side/2} {side/2})" '
           f'xlink:href="data:image/png;base64,{png}"/></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode("ascii")
