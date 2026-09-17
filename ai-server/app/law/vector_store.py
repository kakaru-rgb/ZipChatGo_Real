import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.law.documents import GeneratedLawFile


class VectorStoreUpdateError(RuntimeError):
    """Raised when a new law Vector Store cannot be completely indexed."""


@dataclass(frozen=True)
class VectorStoreBuild:
    vector_store_id: str
    openai_file_ids: tuple[str, ...]


class OpenAIVectorStoreUpdater:
    def __init__(
        self,
        client: Any,
        poll_interval_seconds: float = 2.0,
        timeout_seconds: float = 900.0,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._poll_interval_seconds = poll_interval_seconds
        self._timeout_seconds = timeout_seconds
        self._progress = progress or (lambda _: None)

    def rebuild(
        self,
        files: Sequence[GeneratedLawFile],
        store_name: str,
        build_id: str,
        checkpoint: Callable[[VectorStoreBuild, str], None] | None = None,
    ) -> VectorStoreBuild:
        if not files:
            raise VectorStoreUpdateError("No law documents were generated")

        vector_store = self._client.vector_stores.create(
            name=store_name,
            metadata={"corpus": "zipchatgo-real-estate-law", "build_id": build_id},
        )
        store_id = str(vector_store.id)
        uploaded_file_ids: list[str] = []
        self._progress(f"Created OpenAI Vector Store: {store_id}")
        if checkpoint:
            checkpoint(VectorStoreBuild(store_id, ()), "uploading")

        try:
            for index, generated in enumerate(files, start=1):
                with generated.path.open("rb") as stream:
                    uploaded = self._client.files.create(
                        file=stream,
                        purpose="assistants",
                    )
                file_id = str(uploaded.id)
                uploaded_file_ids.append(file_id)
                self._client.vector_stores.files.create(
                    vector_store_id=store_id,
                    file_id=file_id,
                    attributes=_clean_attributes(generated.attributes),
                    chunking_strategy={
                        "type": "static",
                        "static": {
                            "max_chunk_size_tokens": 1200,
                            "chunk_overlap_tokens": 200,
                        },
                    },
                )
                if checkpoint and (
                    index == 1 or index % 25 == 0 or index == len(files)
                ):
                    checkpoint(
                        VectorStoreBuild(store_id, tuple(uploaded_file_ids)),
                        "uploading",
                    )
                if index == 1 or index % 25 == 0 or index == len(files):
                    self._progress(f"Attached law articles: {index}/{len(files)}")

            self._wait_until_indexed(store_id, len(files))
        except Exception as exception:
            build = VectorStoreBuild(store_id, tuple(uploaded_file_ids))
            raise VectorStoreUpdateError(
                f"Failed to upload or index the new law Vector Store: {exception}"
            ) from _BuildFailure(exception, build)

        build = VectorStoreBuild(store_id, tuple(uploaded_file_ids))
        if checkpoint:
            checkpoint(build, "indexed")
        return build

    def resume(
        self,
        files: Sequence[GeneratedLawFile],
        store_id: str,
        checkpoint: Callable[[VectorStoreBuild, str], None] | None = None,
    ) -> VectorStoreBuild:
        attached = self._list_attached_files(store_id)
        uploaded_file_ids = [str(item.id) for item in attached]
        attached_keys = {
            str((getattr(item, "attributes", None) or {}).get("article_key", ""))
            + ":"
            + str((getattr(item, "attributes", None) or {}).get("law_id", ""))
            for item in attached
        }
        pending = [
            generated
            for generated in files
            if _document_key(generated) not in attached_keys
        ]
        self._progress(
            f"Resuming OpenAI Vector Store: attached={len(attached)}, "
            f"pending={len(pending)}"
        )

        try:
            for index, generated in enumerate(pending, start=1):
                with generated.path.open("rb") as stream:
                    uploaded = self._client.files.create(
                        file=stream,
                        purpose="assistants",
                    )
                file_id = str(uploaded.id)
                uploaded_file_ids.append(file_id)
                self._client.vector_stores.files.create(
                    vector_store_id=store_id,
                    file_id=file_id,
                    attributes=_clean_attributes(generated.attributes),
                    chunking_strategy={
                        "type": "static",
                        "static": {
                            "max_chunk_size_tokens": 1200,
                            "chunk_overlap_tokens": 200,
                        },
                    },
                )
                if checkpoint and (
                    index == 1 or index % 25 == 0 or index == len(pending)
                ):
                    checkpoint(
                        VectorStoreBuild(store_id, tuple(uploaded_file_ids)),
                        "uploading",
                    )
                if index == 1 or index % 25 == 0 or index == len(pending):
                    self._progress(
                        f"Attached remaining law articles: {index}/{len(pending)}"
                    )
            self._wait_until_indexed(store_id, len(files))
        except Exception as exception:
            build = VectorStoreBuild(store_id, tuple(uploaded_file_ids))
            raise VectorStoreUpdateError(
                f"Failed to resume the law Vector Store: {exception}"
            ) from _BuildFailure(exception, build)

        build = VectorStoreBuild(store_id, tuple(uploaded_file_ids))
        if checkpoint:
            checkpoint(build, "indexed")
        return build

    def _list_attached_files(self, store_id: str) -> list[Any]:
        attached: list[Any] = []
        after: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "vector_store_id": store_id,
                "limit": 100,
                "order": "asc",
            }
            if after:
                kwargs["after"] = after
            page = self._client.vector_stores.files.list(**kwargs)
            attached.extend(page.data)
            if not bool(getattr(page, "has_more", False)):
                return attached
            after = str(page.last_id)

    def cleanup(self, build: VectorStoreBuild) -> None:
        try:
            self._client.vector_stores.delete(build.vector_store_id)
        finally:
            for file_id in build.openai_file_ids:
                try:
                    self._client.files.delete(file_id)
                except Exception:
                    self._progress(f"Could not delete failed-build file: {file_id}")

    def _wait_until_indexed(self, store_id: str, expected_count: int) -> None:
        deadline = time.monotonic() + self._timeout_seconds
        while time.monotonic() < deadline:
            store = self._client.vector_stores.retrieve(store_id)
            counts = store.file_counts
            failed = int(getattr(counts, "failed", 0))
            cancelled = int(getattr(counts, "cancelled", 0))
            completed = int(getattr(counts, "completed", 0))
            in_progress = int(getattr(counts, "in_progress", 0))
            total = int(getattr(counts, "total", 0))
            self._progress(
                "Index status: "
                f"completed={completed}, in_progress={in_progress}, "
                f"failed={failed}, total={total}"
            )
            if failed or cancelled:
                raise VectorStoreUpdateError(
                    f"Vector Store indexing failed: failed={failed}, cancelled={cancelled}"
                )
            if completed == expected_count and total == expected_count:
                return
            time.sleep(self._poll_interval_seconds)
        raise VectorStoreUpdateError("Timed out waiting for law Vector Store indexing")


class _BuildFailure(Exception):
    def __init__(self, cause: Exception, build: VectorStoreBuild) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.build = build


def get_failed_build(exception: VectorStoreUpdateError) -> VectorStoreBuild | None:
    cause = exception.__cause__
    return cause.build if isinstance(cause, _BuildFailure) else None


def _clean_attributes(attributes: dict[str, str]) -> dict[str, str]:
    return {
        key: str(value)[:512]
        for key, value in attributes.items()
        if str(value).strip()
    }


def _document_key(generated: GeneratedLawFile) -> str:
    return (
        str(generated.attributes.get("article_key", ""))
        + ":"
        + str(generated.attributes.get("law_id", ""))
    )
