"""JSON load/dump and source SHA-256 for contract documents."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reused_cores.shell3d_linear.types import AnalysisResult, ModelInput


def _reject_non_finite(value: str) -> float:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def dump_json(data: Mapping[str, Any], *, compact: bool = False) -> str:
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def canonical_sha256(data: Mapping[str, Any]) -> str:
    """Content hash of a mapping. Does not match pretty-printed file bytes."""

    return sha256_bytes(dump_json(data, compact=True).encode("utf-8"))


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    data: dict[str, Any]
    sha256: str | None


def _parse_object(text: str) -> dict[str, Any]:
    payload = json.loads(text, parse_constant=_reject_non_finite)
    if not isinstance(payload, dict):
        raise ValueError("contract document must be a JSON object")
    return payload


def load_document(source: str | Path | Mapping[str, Any]) -> LoadedDocument:
    """Load a JSON object and, when possible, the provenance SHA-256.

    File and raw-text inputs hash the original bytes so
    ``AnalysisResult.source.model_sha256`` can match P0 file provenance.
    In-memory mappings defer hashing until a ValidatedModel is built.
    """

    if isinstance(source, Mapping):
        return LoadedDocument(data=dict(source), sha256=None)
    path = Path(source)
    if path.is_file():
        raw = path.read_bytes()
        return LoadedDocument(data=_parse_object(raw.decode("utf-8")), sha256=sha256_bytes(raw))
    text = str(source)
    return LoadedDocument(
        data=_parse_object(text),
        sha256=sha256_bytes(text.encode("utf-8")),
    )


def load_json(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    return load_document(source).data


def model_input_from_mapping(data: Mapping[str, Any]) -> ModelInput:
    return ModelInput.from_dict(data)


def analysis_result_from_mapping(data: Mapping[str, Any]) -> AnalysisResult:
    return AnalysisResult.from_dict(data)


def load_model_input(source: str | Path | Mapping[str, Any]) -> ModelInput:
    return ModelInput.from_dict(load_json(source))


def load_analysis_result(source: str | Path | Mapping[str, Any]) -> AnalysisResult:
    return AnalysisResult.from_dict(load_json(source))


def dump_model_input(model: ModelInput, path: str | Path | None = None) -> str:
    text = dump_json(model.to_dict())
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def dump_analysis_result(result: AnalysisResult, path: str | Path | None = None) -> str:
    text = dump_json(result.to_dict())
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
