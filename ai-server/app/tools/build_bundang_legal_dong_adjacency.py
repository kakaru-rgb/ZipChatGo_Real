"""Build Bundang legal-dong adjacency data from the web-map GeoJSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd

from app.schemas import BUNDANG_LEGAL_DONG_NAME_VALUES


EXPECTED_DONG_COUNT = 18
DEFAULT_INPUT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "main"
    / "resources"
    / "static"
    / "data"
    / "bundang_legal_dong.geojson"
)
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "bundang_legal_dong_adjacency.json"
)


def build_adjacency(
    input_geojson: Path,
    output: Path,
    overwrite: bool = False,
    minimum_shared_boundary_meters: float = 1.0,
) -> dict:
    input_geojson = input_geojson.resolve(strict=True)
    boundaries = gpd.read_file(input_geojson)
    required_columns = {"legal_dong_code", "legal_dong_name", "geometry"}
    missing_columns = required_columns.difference(boundaries.columns)
    if missing_columns:
        raise ValueError(
            f"Missing GeoJSON columns: {sorted(missing_columns)}"
        )
    if boundaries.crs is None:
        raise ValueError("The GeoJSON has no coordinate reference system")
    if len(boundaries) != EXPECTED_DONG_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_DONG_COUNT} Bundang legal dongs, "
            f"found {len(boundaries)}"
        )

    actual_names = set(boundaries["legal_dong_name"])
    expected_names = set(BUNDANG_LEGAL_DONG_NAME_VALUES)
    if actual_names != expected_names:
        raise ValueError("GeoJSON legal-dong names do not match the expected list")
    if boundaries.geometry.isna().any() or boundaries.geometry.is_empty.any():
        raise ValueError("GeoJSON contains null or empty geometry")
    if (~boundaries.geometry.is_valid).any():
        raise ValueError("GeoJSON contains invalid geometry")

    metric_boundaries = boundaries.to_crs(epsg=5186).sort_values(
        "legal_dong_code"
    )
    regions: dict[str, dict] = {}
    for region in metric_boundaries.itertuples(index=False):
        adjacent_regions = []
        for candidate in metric_boundaries.itertuples(index=False):
            if candidate.legal_dong_code == region.legal_dong_code:
                continue

            shared_length = region.geometry.boundary.intersection(
                candidate.geometry.boundary
            ).length
            if shared_length <= minimum_shared_boundary_meters:
                continue

            adjacent_regions.append(
                {
                    "code": str(candidate.legal_dong_code),
                    "name": candidate.legal_dong_name,
                    "shared_boundary_meters": round(shared_length, 1),
                }
            )

        regions[region.legal_dong_name] = {
            "code": str(region.legal_dong_code),
            "adjacent_regions": adjacent_regions,
        }

    payload = {
        "source": input_geojson.name,
        "adjacency_definition": "shared_boundary_longer_than_1_meter",
        "regions": regions,
    }
    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists; use --overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "source": str(input_geojson),
        "count": len(regions),
        "adjacency_pair_count": sum(
            len(region["adjacent_regions"]) for region in regions.values()
        ) // 2,
        "output": str(output.resolve()),
        "output_size_bytes": output.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = build_adjacency(args.input, args.output, args.overwrite)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

