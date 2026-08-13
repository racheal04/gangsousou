from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Job:
    id: str
    title: str
    organization: str = ""
    position: str = ""
    category: str = "身份待核实"
    employment_status: str = "待核实"
    city: str = "江苏"
    district: str = ""
    work_location: str = ""
    source_name: str = ""
    source_url: str = ""
    source_file: str = ""
    source_sheet: str = ""
    source_row: int = 0
    source_code: str = ""
    official: bool = True
    published_at: str = ""
    registration_start: str = ""
    deadline: str = ""
    education: str = ""
    degree: str = ""
    majors: str = ""
    political_status: str = ""
    target_group: str = ""
    experience: str = ""
    other_requirements: str = ""
    physical_test: bool = False
    dispatch: bool = False
    service_years: str = ""
    attachment_urls: list[str] = field(default_factory=list)
    summary: str = ""
    discovered_at: str = ""
    last_seen_at: str = ""
    match: dict[str, Any] = field(default_factory=dict)
    section: str = "趋势参考"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Job":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in raw.items() if key in allowed})


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
