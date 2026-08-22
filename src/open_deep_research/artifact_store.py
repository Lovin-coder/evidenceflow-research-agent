"""Run-scoped storage for normalized Source text outside Graph State."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Protocol, runtime_checkable

from langchain_core.runnables import RunnableConfig

from open_deep_research.configuration import Configuration

ARTIFACT_REF_PREFIX = "artifact:sha256:"


class ArtifactStoreError(ValueError):
    """Report an invalid, missing, or unsafe Source artifact operation."""


@runtime_checkable
class ArtifactStore(Protocol):
    """Store and resolve exact normalized Source text for one owning run."""

    def put_text(self, text: str) -> str:
        """Persist exact text and return an opaque deterministic reference."""

    def get_text(self, artifact_ref: str) -> str:
        """Resolve a previously persisted text reference."""


class LocalFileArtifactStore:
    """Persist normalized Source text in an isolated local run namespace."""

    def __init__(self, root: str | Path, run_id: str) -> None:
        """Create a Store rooted below a deterministic hashed run namespace."""
        if not run_id or not run_id.strip():
            raise ArtifactStoreError("ArtifactStore run_id must not be blank")
        base_root = Path(root).expanduser().resolve()
        run_key = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:24]
        self._root = (base_root / f"run-{run_key}").resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        """Return the isolated filesystem root used by this run."""
        return self._root

    def put_text(self, text: str) -> str:
        """Persist text atomically without rewriting an identical artifact."""
        if not isinstance(text, str) or not text:
            raise ArtifactStoreError("Artifact text must be a non-empty string")
        encoded = text.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        target = self._artifact_path(digest)
        if not target.exists():
            temporary = self._root / f".{digest}.{uuid.uuid4().hex}.tmp"
            try:
                with temporary.open("xb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        return f"{ARTIFACT_REF_PREFIX}{digest}"

    def get_text(self, artifact_ref: str) -> str:
        """Resolve exact UTF-8 text while rejecting malformed references."""
        digest = _parse_artifact_ref(artifact_ref)
        path = self._artifact_path(digest)
        if not path.is_file():
            raise ArtifactStoreError(f"Artifact does not exist: {artifact_ref}")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ArtifactStoreError(
                f"Artifact is not valid UTF-8 text: {artifact_ref}"
            ) from error

    def _artifact_path(self, digest: str) -> Path:
        """Resolve a digest below the run root and enforce path containment."""
        path = (self._root / f"{digest}.txt").resolve()
        if path.parent != self._root:
            raise ArtifactStoreError("Artifact reference escapes the configured root")
        return path


def resolve_artifact_run_id(
    state_run_id: str | None,
    config: RunnableConfig | None,
    *,
    runtime_run_id: object | None = None,
) -> str:
    """Resolve one immutable Artifact namespace for an owning graph run.

    Graph nodes receive copied ``RunnableConfig`` mappings, so mutating a node-local
    mapping cannot communicate a generated identity to later nodes or subgraphs.
    The caller therefore stores this value in internal graph state. An explicit
    configured override wins during bootstrap and must agree with established state;
    otherwise the root runtime ID is used when available, followed by a fresh UUID.

    Args:
        state_run_id: Namespace already carried by internal graph state.
        config: Invocation configuration, including an optional explicit override.
        runtime_run_id: Root node execution ID available only during initial bootstrap.

    Returns:
        A non-blank namespace identity stable for the owning run.

    Raises:
        ArtifactStoreError: If established state conflicts with an explicit override.
    """
    configured_run_id = Configuration.from_runnable_config(config).artifact_run_id
    explicit_run_id = configured_run_id.strip() if configured_run_id else None
    established_run_id = state_run_id.strip() if state_run_id else None
    if established_run_id:
        if explicit_run_id and explicit_run_id != established_run_id:
            raise ArtifactStoreError(
                "Configured artifact_run_id conflicts with the established run namespace"
            )
        return established_run_id
    if explicit_run_id:
        return explicit_run_id
    if runtime_run_id is not None and str(runtime_run_id).strip():
        return f"runtime-{runtime_run_id}"
    return f"run-{uuid.uuid4().hex}"


def artifact_store_from_config(
    config: RunnableConfig | None,
    artifact_run_id: str | None = None,
) -> LocalFileArtifactStore:
    """Build a resolver for an explicit or standalone Artifact namespace.

    Production graph boundaries pass the state-carried ``artifact_run_id``. Direct
    standalone callers receive an isolated call-local namespace unless configuration
    explicitly requests sharing.
    """
    run_id = resolve_artifact_run_id(artifact_run_id, config)
    configurable = Configuration.from_runnable_config(config)
    return LocalFileArtifactStore(configurable.artifact_store_root, run_id)


def _parse_artifact_ref(artifact_ref: str) -> str:
    """Extract and validate the SHA-256 digest from an opaque local reference."""
    if not artifact_ref.startswith(ARTIFACT_REF_PREFIX):
        raise ArtifactStoreError(f"Invalid artifact reference: {artifact_ref!r}")
    digest = artifact_ref.removeprefix(ARTIFACT_REF_PREFIX)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ArtifactStoreError(f"Invalid artifact reference: {artifact_ref!r}")
    return digest
