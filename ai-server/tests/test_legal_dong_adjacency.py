import json
from pathlib import Path

import pytest

from app.schemas import BUNDANG_LEGAL_DONG_NAME_VALUES
from app.tools.legal_dong_adjacency import (
    LegalDongAdjacencyError,
    LegalDongAdjacencyTool,
)


def test_lookup_returns_geojson_derived_neighbors_for_pangyo() -> None:
    result = LegalDongAdjacencyTool().lookup({"region_name": "판교동"})

    assert result["region"] == {
        "code": "41135108",
        "name": "판교동",
        "full_name": "경기도 성남시 분당구 판교동",
    }
    assert result["adjacent_count"] == 4
    assert {region["name"] for region in result["adjacent_regions"]} == {
        "삼평동",
        "백현동",
        "운중동",
        "하산운동",
    }
    assert all(
        region["shared_boundary_meters"] > 1
        for region in result["adjacent_regions"]
    )


def test_default_data_has_symmetric_adjacency_for_all_18_dongs() -> None:
    tool = LegalDongAdjacencyTool()
    results = {
        name: tool.lookup({"region_name": name})
        for name in BUNDANG_LEGAL_DONG_NAME_VALUES
    }

    assert len(results) == 18
    for name, result in results.items():
        for adjacent in result["adjacent_regions"]:
            reverse_names = {
                item["name"]
                for item in results[adjacent["name"]]["adjacent_regions"]
            }
            assert name in reverse_names


def test_lookup_rejects_unknown_legal_dong() -> None:
    with pytest.raises(
        LegalDongAdjacencyError,
        match="Invalid legal-dong adjacency arguments",
    ):
        LegalDongAdjacencyTool().lookup({"region_name": "강남동"})


def test_tool_rejects_incomplete_data(tmp_path: Path) -> None:
    data_path = tmp_path / "adjacency.json"
    data_path.write_text(
        json.dumps(
            {
                "source": "test.geojson",
                "adjacency_definition": "shared_boundary_longer_than_1_meter",
                "regions": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        LegalDongAdjacencyError,
        match="does not contain all Bundang legal dongs",
    ):
        LegalDongAdjacencyTool(data_path)
