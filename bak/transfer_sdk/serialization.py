from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Any

from .encoding import TransferJob, job_to_dict
from .spool import job_from_dict


class JobValidationError(Exception):
    """Raised when an inbound job payload cannot be parsed."""


@dataclass(frozen=True)
class JobPayload:
    """Normalized representation of a transfer job message."""

    raw_text: str
    job: TransferJob
    normalized: Dict[str, Any]
    normalized_text: str


def _parse_json_message(message: str) -> Dict[str, Any]:
    try:
        data = json.loads(message)
    except json.JSONDecodeError as exc:
        raise JobValidationError("invalid JSON payload") from exc
    if not isinstance(data, dict):
        raise JobValidationError("job payload must be an object")
    return data


def decode_job_message(message: str) -> JobPayload:
    """Validate and normalize an incoming job message."""
    data = _parse_json_message(message)
    job = job_from_dict(data)
    normalized = job_to_dict(job)
    normalized_text = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False)
    return JobPayload(
        raw_text=message,
        job=job,
        normalized=normalized,
        normalized_text=normalized_text,
    )


def encode_job(job: TransferJob) -> str:
    """Serialize a TransferJob into the canonical JSON representation."""
    normalized = job_to_dict(job)
    return json.dumps(normalized, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "JobPayload",
    "JobValidationError",
    "decode_job_message",
    "encode_job",
]
