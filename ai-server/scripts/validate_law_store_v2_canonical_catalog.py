from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.canonical_catalog_law_experiment import (
    detect_canonical_law_article_pairs,
    detect_canonical_law_names,
)
from app.evaluation.canonical_law_catalog import CanonicalLawCatalog
from app.law.targets import LAW_TARGETS


DEFAULT_ARTIFACT = Path(
    r"C:\ajb\2025_exam\law_rag_vector_store_builds\20260914T030618795400Z"
) / "new_store_files.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline validation of the frozen law_store_v2 canonical catalog."
    )
    parser.add_argument("--catalog-json", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    catalog = CanonicalLawCatalog.from_new_store_files(
        args.catalog_json,
        corpus_version="law_store_v2",
        expected_file_count=5658,
        expected_law_count=49,
    )
    legacy_names = {target.name for target in LAW_TARGETS}
    unsupported = {"민사집행법", "장사 등에 관한 법률"}
    representative = (
        "부동산 실권리자명의 등기에 관한 법률",
        "부동산 실권리자명의 등기에 관한 법률 시행령",
        "부동산 실권리자명의 등기에 관한 법률 시행규칙",
    )

    checks = {
        "catalog_file_count": catalog.file_count == 5658,
        "catalog_law_count": len(catalog.law_names) == 49,
        "unique_law_article_pair_count": len(catalog.law_article_pairs) == 5658,
        "legacy_15_present": legacy_names.issubset(catalog.law_names),
        "new_family_present": all(catalog.contains_law(name) for name in representative),
        "new_family_exact_metadata_present": catalog.contains_pair(
            representative[0], "제4조"
        ),
        "unsupported_absent": all(not catalog.contains_law(name) for name in unsupported),
        "new_name_detection": detect_canonical_law_names(
            representative[0] + " 제4조", catalog
        ) == [representative[0]],
        "new_pair_detection": [
            pair.as_dict()
            for pair in detect_canonical_law_article_pairs(
                representative[0] + " 제4조", catalog
            )
        ] == [{"law_name": representative[0], "article_number": "제4조"}],
        "article_subnumber_detection": [
            pair.article_number
            for pair in detect_canonical_law_article_pairs(
                representative[2] + " 제6조의2", catalog
            )
        ] == ["제6조의2"],
        "unsupported_not_detected": detect_canonical_law_names(
            "민사집행법과 장사 등에 관한 법률", catalog
        ) == [],
        "alias_not_added": detect_canonical_law_names("부동산실명법 제4조", catalog) == [],
    }

    digest = hashlib.sha256(args.catalog_json.read_bytes()).hexdigest().upper()
    print(f"CorpusVersion={catalog.corpus_version}")
    print(f"Artifact={catalog.source_path}")
    print(f"ArtifactSHA256={digest}")
    print(f"Files={catalog.file_count}")
    print(f"CanonicalLawNames={len(catalog.law_names)}")
    for name, passed in checks.items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
