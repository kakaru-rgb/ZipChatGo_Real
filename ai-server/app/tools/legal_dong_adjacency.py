"""Look up legal dongs that share a boundary within Bundang-gu."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    BUNDANG_LEGAL_DONG_NAME_VALUES,
    AdjacentLegalDongArguments,
)


DEFAULT_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "bundang_legal_dong_adjacency.json"
)


class LegalDongAdjacencyError(RuntimeError):
    """Raised when legal-dong adjacency data cannot provide a valid result."""


class LegalDongAdjacencyTool:
    def __init__(self, data_path: Path = DEFAULT_DATA_PATH) -> None:
        self._data_path = data_path
        self._data = self._load_data()

    def lookup(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            arguments = AdjacentLegalDongArguments.model_validate(raw_arguments)
        except ValidationError as exception:
            raise LegalDongAdjacencyError(
                "Invalid legal-dong adjacency arguments"
            ) from exception

        region = self._data["regions"].get(arguments.region_name)
        if not isinstance(region, dict):
            raise LegalDongAdjacencyError(
                f"Legal dong is not present in adjacency data: {arguments.region_name}"
            )

        adjacent_regions = region["adjacent_regions"]
        return {
            "source": self._data["source"],
            "adjacency_definition": self._data["adjacency_definition"],
            "region": {
                "code": region["code"],
                "name": arguments.region_name,
                "full_name": f"경기도 성남시 분당구 {arguments.region_name}",
            },
            "adjacent_count": len(adjacent_regions),
            "adjacent_regions": adjacent_regions,
        }

    def _load_data(self) -> dict[str, Any]:
        try:
            payload = json.loads(self._data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exception:
            raise LegalDongAdjacencyError(
                "Legal-dong adjacency data could not be loaded"
            ) from exception

        regions = payload.get("regions")
        if not isinstance(regions, dict):
            raise LegalDongAdjacencyError("Adjacency data has no regions object")

        expected_names = set(BUNDANG_LEGAL_DONG_NAME_VALUES)
        if set(regions) != expected_names:
            raise LegalDongAdjacencyError(
                "Adjacency data does not contain all Bundang legal dongs"
            )

        for name, region in regions.items():
            self._validate_region(name, region, expected_names)

        return payload

    @staticmethod
    def _validate_region(
        name: str,
        region: Any,
        expected_names: set[str],
    ) -> None:
        if not isinstance(region, dict):
            raise LegalDongAdjacencyError(f"Invalid adjacency region: {name}")
        if not isinstance(region.get("code"), str):
            raise LegalDongAdjacencyError(f"Invalid legal-dong code: {name}")

        adjacent_regions = region.get("adjacent_regions")
        if not isinstance(adjacent_regions, list):
            raise LegalDongAdjacencyError(f"Invalid adjacent region list: {name}")

        adjacent_names: set[str] = set()
        for adjacent in adjacent_regions:
            if not isinstance(adjacent, dict):
                raise LegalDongAdjacencyError(f"Invalid adjacent region: {name}")
            adjacent_name = adjacent.get("name")
            boundary_length = adjacent.get("shared_boundary_meters")
            if (
                adjacent_name not in expected_names
                or adjacent_name == name
                or adjacent_name in adjacent_names
                or not isinstance(adjacent.get("code"), str)
                or not isinstance(boundary_length, (int, float))
                or boundary_length <= 1
            ):
                raise LegalDongAdjacencyError(
                    f"Invalid adjacent region entry: {name} -> {adjacent_name}"
                )
            adjacent_names.add(adjacent_name)

