from __future__ import annotations

import json
from pathlib import Path

from .attachments import jobs_from_spreadsheet


def import_local_files(directory: Path) -> list:
    registry_path = Path(__file__).resolve().parents[2] / "config" / "local_sources.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    jobs = []
    for path in sorted(directory.glob("*.xls*")):
        name = path.name
        default_category = "公务员" if "公务员" in name or "考录职位" in name else "事业单位"
        default_city = next((city for city in ("苏州", "南京", "无锡", "南通", "常州", "扬州", "镇江", "徐州", "盐城", "泰州", "淮安", "宿迁", "连云港") if city in name), "江苏")
        meta = {
            "category": default_category,
            "employment_status": "编内",
            "city": default_city,
            "source_name": name,
            "source_url": "",
            "official": True,
            "published_at": "",
            **registry.get(name, {}),
        }
        jobs.extend(jobs_from_spreadsheet(path, meta))
    return jobs
