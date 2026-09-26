"""Artifacts belong to a claim, never to a mutable source slot."""

from uuid import UUID


def annotated_object_key(job_id: int, attempt: int, claim_token: str) -> str:
    token = str(UUID(claim_token))
    if job_id < 1 or attempt < 1:
        raise ValueError("Invalid job or attempt")
    return f"annotated/jobs/{job_id}/attempts/{attempt}/{token}.jpg"
