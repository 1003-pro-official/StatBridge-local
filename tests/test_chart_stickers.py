"""Sticker asset, rendering and HTTP history contracts with synthetic observations."""
import base64
import copy
import json
import math
import struct
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/agent"))
from chart_stickers import ASSET_ROOT, sticker_catalog, sticker_source
from output_schema import ChartSpec, ChartSticker, ChartEditCommand
from test_chart_edit_period_and_box import fixture_session


def sticker(**kwargs):
    return {"id":"test-sticker", "asset_id":"report-arrow-up", "x":.35, "y":.7,
            "size":.4, "angle":45, "opacity":.8, **kwargs}

def test_retired_images_do_not_break_saved_graph_state():
    state=ChartSpec.model_validate({'title':'보존할 제목','stickers':[sticker(asset_id='sticker-5-03'),sticker(id='new',asset_id='report-arrow-up')]})
    assert state.title=='보존할 제목'
    assert [s.asset_id for s in state.stickers]==['report-arrow-up']
    with pytest.raises(ValueError):ChartSpec.model_validate({'stickers':[sticker(asset_id='unknown-image')]})


def test_catalog_is_complete_and_every_png_has_real_transparency():
    catalog=sticker_catalog()
    assert len(catalog)==2 and len({a["id"] for a in catalog})==2
    assert len({a["category"] for a in catalog})==1
    assert set(a["file"] for a in catalog)=={p.name for p in ASSET_ROOT.glob("*.png")}
    for asset in catalog:
        data=(ASSET_ROOT/asset["file"]).read_bytes()
        assert data[:8]==b"\x89PNG\r\n\x1a\n"
        width,height,depth,color=struct.unpack(">IIBB",data[16:26])
        assert (width,height)==(asset["width"],asset["height"])
        assert depth==8 and color==6  # RGBA, not opaque RGB with painted background
        compressed=b"";offset=8
        while offset<len(data):
            length=struct.unpack(">I",data[offset:offset+4])[0]
            if data[offset+4:offset+8]==b"IDAT":compressed+=data[offset+8:offset+8+length]
            offset+=length+12
        # Entire eight-pixel padding row is transparent; PNG filters preserve zeros.
        raw=zlib.decompress(compressed)
        assert not any(raw[1:1+width*4])


@pytest.mark.parametrize("change",[{"asset_id":"../.env"},{"asset_id":"https://example.com/a.png"},
    {"size":0},{"size":2},{"angle":361},{"x":-1},{"y":2},{"angle":math.nan},
    {"size":math.inf},{"opacity":1.1},{"source":"file:///etc/passwd"}])
def test_invalid_stickers_are_rejected(change):
    with pytest.raises(ValueError):ChartSticker.model_validate(sticker(**change))


def test_duplicate_ids_and_item_limit_are_rejected():
    with pytest.raises(ValueError):ChartSpec(stickers=[sticker(),sticker()])
    with pytest.raises(ValueError):ChartSpec(stickers=[sticker(id=f"s{i}") for i in range(41)])


def test_rotated_svg_is_self_contained_and_does_not_clip_artwork():
    source=sticker_source("report-arrow-up",137)
    svg=ET.fromstring(base64.b64decode(source.split(",",1)[1]))
    image=svg[0]
    side=float(svg.attrib["width"])
    assert side>=math.hypot(float(image.attrib["width"]),float(image.attrib["height"]))
    assert image.attrib["transform"].startswith("rotate(137 ")
    embedded=image.attrib["{http://www.w3.org/1999/xlink}href"]
    assert base64.b64decode(embedded.split(",",1)[1])==(ASSET_ROOT/"report-arrow-up.png").read_bytes()


def test_stickers_preserve_data_and_survive_period_redraw_and_style_reset():
    output,session=fixture_session();initial=session["output"];data=copy.deepcopy(session["result"])
    edited=output.apply_edits(data,initial,[ChartEditCommand(operation="set_stickers",kind="STYLE_EDIT",params={"items":[sticker()]})],generate_explanation=False)
    assert edited["table"]==initial["table"] and data==session["result"]
    image=edited["plotlyFigure"]["layout"]["images"][0]
    assert image["xref"]==image["yref"]=="paper" and image["opacity"]==.8
    assert image["source"]==sticker_source("report-arrow-up",45)
    data["execution"]["rows"].insert(0,{**data["execution"]["rows"][0],"PRD_DE":"201501","DT":"5"})
    redraw=output._build(data,ChartSpec.model_validate(edited["chartState"]),generate_explanation=False)
    assert redraw["plotlyFigure"]["layout"]["images"]==edited["plotlyFigure"]["layout"]["images"]
    reset=output.apply_edits(data,redraw,[ChartEditCommand(operation="reset_styles",kind="STYLE_EDIT")],generate_explanation=False)
    assert reset["chartState"]["stickers"]==[] and not reset["plotlyFigure"]["layout"].get("images")


def test_http_sticker_edits_skip_model_and_support_undo_redo_and_delete(monkeypatch):
    from authenticated_client import TestClient
    import bridge_api as api
    output,session=fixture_session();baseline=copy.deepcopy(session)
    monkeypatch.setattr(api.agent,"output_agent",output)
    monkeypatch.setattr(api,"_table_card",lambda tid:{"tableId":tid})
    def forbidden(*args,**kwargs):raise AssertionError("Direct sticker manipulation must not call a provider")
    monkeypatch.setattr(api.edit_agent,"edit",forbidden)
    monkeypatch.setattr(api.agent,"execute_resolution",forbidden)
    monkeypatch.setitem(api.EDIT_SESSIONS,"stickers-http",session)
    client=TestClient(api.app)
    assert len(client.get("/api/stickers").json()["items"])==2
    def request(**payload):return client.post("/api/output/edit",json={"edit_session_id":"stickers-http",**payload})
    added=request(stickers=[sticker()],revision=0)
    assert added.status_code==200,added.text
    assert added.json()["outputSpec"]["chartState"]["stickers"]==[sticker()]
    assert request(stickers=[],revision=0).status_code==409
    before=copy.deepcopy(session)
    assert request(stickers=[sticker(id="bad",asset_id="unknown")],revision=1).status_code==422
    assert request(stickers=[],action="undo",revision=1).status_code==422
    assert request(stickers=[sticker(),sticker()],revision=1).status_code==422
    assert session==before
    undone=request(action="undo",revision=1)
    assert undone.status_code==200 and undone.json()["outputSpec"]["chartState"]==baseline["output"]["chartState"]
    redone=request(action="redo",revision=2)
    assert redone.status_code==200 and redone.json()["outputSpec"]["chartState"]["stickers"]==[sticker()]
    resized=request(stickers=[sticker(size=.7,angle=-125,x=.2)],revision=3)
    assert resized.status_code==200 and resized.json()["outputSpec"]["chartState"]["stickers"][0]["angle"]==-125
    removed=request(stickers=[],revision=4)
    assert removed.status_code==200 and removed.json()["outputSpec"]["chartState"]["stickers"]==[]
    assert session["result"]==baseline["result"]


def test_pending_stickers_and_text_edit_are_atomic_and_survive_later_edits(monkeypatch):
    from authenticated_client import TestClient
    import bridge_api as api
    output,session=fixture_session()
    monkeypatch.setattr(api.agent,"output_agent",output)
    monkeypatch.setattr(api,"_table_card",lambda tid:{"tableId":tid})
    monkeypatch.setitem(api.EDIT_SESSIONS,"stickers-combined",session)
    seen=[]
    def edit(result,baseline,instruction,visual):
        seen.append(copy.deepcopy(baseline["chartState"]["stickers"]))
        if instruction=="fail": raise ValueError("invalid edit")
        return output.apply_edits(result,baseline,[ChartEditCommand(operation="set_title",kind="STYLE_EDIT",value=instruction)],generate_explanation=False)
    monkeypatch.setattr(api.edit_agent,"edit",edit)
    client=TestClient(api.app)
    def request(**payload):return client.post("/api/output/edit",json={"edit_session_id":"stickers-combined",**payload})
    placed=[sticker(x=.27,y=.64,angle=135,size=.22)]
    first=request(stickers=placed,instruction="new title",revision=0)
    assert first.status_code==200,first.text
    state=first.json()["outputSpec"]["chartState"]
    assert state["title"]=="new title" and state["stickers"]==placed
    second=request(instruction="next title",revision=1)
    assert second.status_code==200,second.text
    assert second.json()["outputSpec"]["chartState"]["stickers"]==placed
    assert seen==[placed,placed]
    before=copy.deepcopy(session)
    assert request(stickers=[sticker(x=.9)],instruction="fail",revision=2).status_code==422
    assert session==before
    undo=request(action="undo",revision=2)
    assert undo.status_code==200 and undo.json()["outputSpec"]["chartState"]["stickers"]==placed
    undo=request(action="undo",revision=3)
    assert undo.status_code==200 and undo.json()["outputSpec"]["chartState"]["stickers"]==[]
