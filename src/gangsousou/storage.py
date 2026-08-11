from __future__ import annotations

import json
from pathlib import Path

from .models import Job, now_iso


def load_jobs(path: Path) -> dict[str, Job]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: Job.from_dict(item) for item in raw.get("jobs", [])}


def merge_jobs(existing: dict[str, Job], incoming: list[Job]) -> tuple[dict[str, Job], list[Job]]:
    new_jobs: list[Job] = []
    for job in incoming:
        if job.id in existing:
            original = existing[job.id]
            job.discovered_at = original.discovered_at or job.discovered_at
        else:
            new_jobs.append(job)
        existing[job.id] = job
    return existing, new_jobs


def save_jobs(path: Path, jobs: dict[str, Job], source_runs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        jobs.values(),
        key=lambda job: (job.published_at, job.discovered_at, job.match.get("score", 0)),
        reverse=True,
    )
    payload = {
        "generated_at": now_iso(),
        "total": len(ordered),
        "source_runs": source_runs,
        "jobs": [job.to_dict() for job in ordered],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

