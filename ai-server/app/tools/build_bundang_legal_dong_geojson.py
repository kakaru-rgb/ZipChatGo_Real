"""Build a web-map GeoJSON containing Bundang-gu legal-dong boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import geopandas as gpd
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.ops import unary_union
from shapely.validation import explain_validity


BUNDANG_LEGAL_DONG_CODE_PREFIX = "41135"
EXPECTED_DONG_COUNT = 18
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "main"
    / "resources"
    / "static"
    / "data"
    / "bundang_legal_dong.geojson"
)


def _find_shapefile(input_zip: Path) -> str:
    with ZipFile(input_zip) as archive:
        shapefiles = [name for name in archive.namelist() if name.lower().endswith(".shp")]

    if len(shapefiles) != 1:
        raise ValueError(
            f"Expected exactly one SHP file in {input_zip}, found {shapefiles}"
        )
    return shapefiles[0]


def _polygonal_only(geometry: object) -> Polygon | MultiPolygon:
    if isinstance(geometry, (Polygon, MultiPolygon)):
        return geometry
    if isinstance(geometry, GeometryCollection):
        polygon_parts = [
            part
            for part in geometry.geoms
            if isinstance(part, (Polygon, MultiPolygon)) and not part.is_empty
        ]
        if polygon_parts:
            merged = unary_union(polygon_parts)
            if isinstance(merged, (Polygon, MultiPolygon)):
                return merged
    raise ValueError("Geometry repair did not produce a Polygon or MultiPolygon")


def build_geojson(input_zip: Path, output: Path, overwrite: bool = False) -> dict:
    input_zip = input_zip.resolve(strict=True)
    source_shapefile = _find_shapefile(input_zip)

    boundaries = gpd.read_file(input_zip, encoding="cp949")
    required_columns = {"EMD_CD", "EMD_NM", "geometry"}
    missing_columns = required_columns.difference(boundaries.columns)
    if missing_columns:
        raise ValueError(f"Missing required SHP columns: {sorted(missing_columns)}")
    if boundaries.crs is None:
        raise ValueError("The source SHP has no coordinate reference system")

    source_crs = boundaries.crs.to_string()
    bundang = boundaries[
        boundaries["EMD_CD"].astype(str).str.startswith(BUNDANG_LEGAL_DONG_CODE_PREFIX)
    ].copy()
    bundang = bundang.sort_values("EMD_CD").reset_index(drop=True)

    if len(bundang) != EXPECTED_DONG_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_DONG_COUNT} Bundang legal dongs, found {len(bundang)}"
        )
    if bundang.geometry.isna().any() or bundang.geometry.is_empty.any():
        raise ValueError("Bundang boundaries contain null or empty geometry")

    invalid_before = bundang.loc[~bundang.geometry.is_valid, ["EMD_CD", "EMD_NM", "geometry"]]
    invalid_details = [
        {
            "code": row.EMD_CD,
            "name": row.EMD_NM,
            "reason": explain_validity(row.geometry),
        }
        for row in invalid_before.itertuples(index=False)
    ]

    if invalid_details:
        bundang.geometry = bundang.geometry.make_valid().map(_polygonal_only)

    if (~bundang.geometry.is_valid).any():
        raise ValueError("Invalid geometry remains after make_valid()")
    unsupported_types = sorted(
        set(bundang.geometry.geom_type).difference({"Polygon", "MultiPolygon"})
    )
    if unsupported_types:
        raise ValueError(f"Unsupported geometry types remain: {unsupported_types}")

    bundang = bundang.to_crs(epsg=4326)
    result = bundang[["EMD_CD", "EMD_NM", "geometry"]].rename(
        columns={"EMD_CD": "legal_dong_code", "EMD_NM": "legal_dong_name"}
    )

    if output.exists() and not overwrite:
        raise FileExistsError(f"Output already exists; use --overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        result.to_json(drop_id=True, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "source_archive": str(input_zip),
        "source_shapefile": source_shapefile,
        "source_crs": source_crs,
        "target_crs": result.crs.to_string(),
        "count": len(result),
        "legal_dong_names": result["legal_dong_name"].tolist(),
        "geometry_types": result.geometry.geom_type.value_counts().to_dict(),
        "invalid_before": invalid_details,
        "invalid_after": int((~result.geometry.is_valid).sum()),
        "output": str(output.resolve()),
        "output_size_bytes": output.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_zip", type=Path, help="Path to the original SHP ZIP")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = build_geojson(args.input_zip, args.output, args.overwrite)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
