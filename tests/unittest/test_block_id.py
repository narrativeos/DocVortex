from __future__ import annotations

from _span_test_utils import inline

from docvortex.postprocess.document import model_json_to_middle_json
from docvortex.schema import BlockType, MiddleJson, ModelJson, Producer, TextBlock


def _text_block_payload(block_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": BlockType.TEXT,
        "content": inline("body"),
        "bbox": [0.1, 0.1, 0.9, 0.2],
    }
    if block_id is not None:
        payload["block_id"] = block_id
    return payload


def test_block_id_round_trips_through_block_model() -> None:
    """block_id 作为一等字段被接受、保留并在序列化中输出。"""
    block = TextBlock.model_validate(_text_block_payload("918ebde3-ce3e-5d40-a013-6091106bfa2a"))
    assert block.block_id == "918ebde3-ce3e-5d40-a013-6091106bfa2a"
    dumped = block.model_dump(mode="json", exclude_defaults=True)
    assert dumped["block_id"] == "918ebde3-ce3e-5d40-a013-6091106bfa2a"


def test_block_id_defaults_to_none_and_is_omitted_on_serialization() -> None:
    """未提供 block_id 时字段为 None，skip_defaults 序列化不输出该键。"""
    block = TextBlock.model_validate(_text_block_payload())
    assert block.block_id is None
    dumped = block.model_dump(mode="json", exclude_defaults=True)
    assert "block_id" not in dumped


def test_middle_json_preserves_block_id_per_block() -> None:
    """MiddleJson 逐 block 保留 block_id，缺失 block 不输出该键。"""
    middle = MiddleJson(
        pages=[
            {
                "page_idx": 0,
                "blocks": [
                    {**_text_block_payload("id-a"), "index": 0},
                    {**_text_block_payload(), "index": 1},
                ],
            }
        ],
        is_full_document=True,
        metadata={"file_suffix": "pdf", "producer": Producer(name="docvortex", version="test")},
        extensions={},
    )
    blocks = middle.pages[0].blocks
    assert blocks[0].block_id == "id-a"
    assert blocks[1].block_id is None
    payload = middle.to_dict(skip_defaults=True)
    assert payload["pages"][0]["blocks"][0]["block_id"] == "id-a"
    assert "block_id" not in payload["pages"][0]["blocks"][1]


def test_model_json_to_middle_json_carries_block_id() -> None:
    """postprocess 转换保留 raw block 上的 block_id。"""
    model_json = ModelJson(
        pages=[[_text_block_payload("918ebde3-ce3e-5d40-a013-6091106bfa2a")]],
        page_index_map=[],
        metadata={"file_suffix": "pdf", "producer": Producer(name="mineru", version="test")},
        extensions={},
    )
    middle = model_json_to_middle_json(model_json)
    assert middle.pages[0].blocks[0].block_id == "918ebde3-ce3e-5d40-a013-6091106bfa2a"


def test_visual_parent_block_inherits_main_block_id() -> None:
    """视觉重组后父块继承主体的 block_id，子块各自保留。"""
    model_json = ModelJson(
        pages=[
            [
                {
                    "type": BlockType.IMAGE,
                    "content": "",
                    "bbox": [0.1, 0.1, 0.5, 0.5],
                    "block_id": "main-id",
                },
                {
                    "type": "image_caption",
                    "content": inline("caption"),
                    "bbox": [0.1, 0.51, 0.5, 0.55],
                    "block_id": "caption-id",
                },
            ]
        ],
        page_index_map=[],
        metadata={"file_suffix": "pdf", "producer": Producer(name="mineru", version="test")},
        extensions={},
    )
    middle = model_json_to_middle_json(model_json)
    (image_block,) = middle.pages[0].blocks
    assert image_block.type == BlockType.IMAGE
    assert image_block.block_id == "main-id"
    assert [child.block_id for child in image_block.content] == ["main-id", "caption-id"]
