from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CanonicalLawCatalog:
    """Immutable, offline catalog derived only from frozen Store artifacts."""

    corpus_version: str
    source_path: Path
    file_count: int
    law_names: tuple[str, ...]
    law_article_pairs: frozenset[tuple[str, str]]

    @classmethod
    def from_new_store_files(
        cls,
        source_path: str | Path,
        *,
        corpus_version: str,
        expected_file_count: int | None = None,
        expected_law_count: int | None = None,
    ) -> "CanonicalLawCatalog":
        path = Path(source_path).resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("new_store_files artifact must contain a JSON list")

        names: set[str] = set()
        pairs: set[tuple[str, str]] = set()
        for index, record in enumerate(payload, start=1):
            attributes = record.get("attributes") if isinstance(record, dict) else None
            if not isinstance(attributes, dict):
                raise ValueError(f"record {index} has no attributes object")
            law_name = _required_text(attributes, "law_name", index)
            article_number = _canonical_article_number(
                _required_text(attributes, "article_number", index)
            )
            names.add(law_name)
            pairs.add((law_name, article_number))

        if expected_file_count is not None and len(payload) != expected_file_count:
            raise ValueError(
                f"unexpected file count: expected {expected_file_count}, got {len(payload)}"
            )
        if expected_law_count is not None and len(names) != expected_law_count:
            raise ValueError(
                f"unexpected law count: expected {expected_law_count}, got {len(names)}"
            )

        return cls(
            corpus_version=corpus_version,
            source_path=path,
            file_count=len(payload),
            law_names=tuple(sorted(names)),
            law_article_pairs=frozenset(pairs),
        )

    @classmethod
    def from_records(
        cls,
        records: Iterable[dict[str, Any]],
        *,
        corpus_version: str = "test",
    ) -> "CanonicalLawCatalog":
        """Small-fixture constructor for offline unit tests only."""

        payload = list(records)
        names: set[str] = set()
        pairs: set[tuple[str, str]] = set()
        for index, record in enumerate(payload, start=1):
            law_name = _required_text(record, "law_name", index)
            article_number = _canonical_article_number(
                _required_text(record, "article_number", index)
            )
            names.add(law_name)
            pairs.add((law_name, article_number))
        return cls(
            corpus_version=corpus_version,
            source_path=Path("<unit-test-fixture>"),
            file_count=len(payload),
            law_names=tuple(sorted(names)),
            law_article_pairs=frozenset(pairs),
        )

    def contains_law(self, law_name: str) -> bool:
        return law_name in self.law_names

    def contains_pair(self, law_name: str, article_number: str) -> bool:
        return (law_name, _canonical_article_number(article_number)) in self.law_article_pairs


class CorpusScope(StrEnum):
    IN_SCOPE = "in_scope"
    PARTIAL_SCOPE = "partial_scope"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class OfflineScopeRequirements:
    """Human-reviewed post-evaluation evidence; never an Agent input."""

    required_law_names: tuple[str, ...] = ()
    required_law_article_pairs: tuple[tuple[str, str], ...] = ()
    additional_external_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class OfflineScopeResult:
    scope: CorpusScope
    missing_law_names: tuple[str, ...]
    missing_law_article_pairs: tuple[tuple[str, str], ...]
    additional_external_sources: tuple[str, ...]


def classify_offline_scope(
    catalog: CanonicalLawCatalog,
    requirements: OfflineScopeRequirements,
) -> OfflineScopeResult:
    """Classify corpus coverage without reading question text or official answers."""

    missing_laws = tuple(
        name for name in requirements.required_law_names if not catalog.contains_law(name)
    )
    missing_pairs = tuple(
        (law_name, _canonical_article_number(article_number))
        for law_name, article_number in requirements.required_law_article_pairs
        if not catalog.contains_pair(law_name, article_number)
    )
    if missing_laws or missing_pairs:
        scope = CorpusScope.OUT_OF_SCOPE
    elif requirements.additional_external_sources:
        scope = CorpusScope.PARTIAL_SCOPE
    else:
        scope = CorpusScope.IN_SCOPE
    return OfflineScopeResult(
        scope=scope,
        missing_law_names=missing_laws,
        missing_law_article_pairs=missing_pairs,
        additional_external_sources=requirements.additional_external_sources,
    )


def _required_text(attributes: dict[str, Any], key: str, index: int) -> str:
    value = str(attributes.get(key, "")).strip()
    if not value:
        raise ValueError(f"record {index} has blank {key}")
    return value


def _canonical_article_number(value: str) -> str:
    return "".join(value.split())
