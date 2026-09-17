from __future__ import annotations

import json

import pytest

from app.evaluation.canonical_law_catalog import (
    CanonicalLawCatalog,
    CorpusScope,
    OfflineScopeRequirements,
    classify_offline_scope,
)


def test_loads_only_canonical_metadata_from_frozen_artifact(tmp_path) -> None:
    artifact = tmp_path / "new_store_files.json"
    artifact.write_text(
        json.dumps(
            [
                {
                    "file_id": "file-1",
                    "attributes": {
                        "law_name": "민법",
                        "article_number": "제 6 조의 2",
                    },
                },
                {
                    "file_id": "file-2",
                    "attributes": {
                        "law_name": "부동산 실권리자명의 등기에 관한 법률",
                        "article_number": "제4조",
                    },
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    catalog = CanonicalLawCatalog.from_new_store_files(
        artifact,
        corpus_version="law_store_v2",
        expected_file_count=2,
        expected_law_count=2,
    )

    assert catalog.file_count == 2
    assert catalog.contains_law("부동산 실권리자명의 등기에 관한 법률")
    assert catalog.contains_pair("민법", "제6조의2")


def test_rejects_blank_required_metadata(tmp_path) -> None:
    artifact = tmp_path / "new_store_files.json"
    artifact.write_text(
        json.dumps([{"attributes": {"law_name": "민법", "article_number": ""}}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="blank article_number"):
        CanonicalLawCatalog.from_new_store_files(
            artifact,
            corpus_version="law_store_v2",
        )


def test_scope_classification_uses_only_reviewed_requirements(catalog) -> None:
    in_scope = classify_offline_scope(
        catalog,
        OfflineScopeRequirements(
            required_law_article_pairs=(("공인중개사법", "제6조"),),
        ),
    )
    partial = classify_offline_scope(
        catalog,
        OfflineScopeRequirements(
            required_law_names=("민법",),
            additional_external_sources=("판례",),
        ),
    )
    out_of_scope = classify_offline_scope(
        catalog,
        OfflineScopeRequirements(required_law_names=("민사집행법",)),
    )

    assert in_scope.scope is CorpusScope.IN_SCOPE
    assert partial.scope is CorpusScope.PARTIAL_SCOPE
    assert out_of_scope.scope is CorpusScope.OUT_OF_SCOPE
    assert out_of_scope.missing_law_names == ("민사집행법",)


@pytest.fixture
def catalog() -> CanonicalLawCatalog:
    return CanonicalLawCatalog.from_records(
        [
            {"law_name": "공인중개사법", "article_number": "제6조"},
            {"law_name": "민법", "article_number": "제563조"},
        ]
    )
