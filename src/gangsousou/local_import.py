from __future__ import annotations

from pathlib import Path

from .attachments import jobs_from_spreadsheet


def import_local_files(directory: Path) -> list:
    jobs = []
    for path in sorted(directory.glob("*.xls*")):
        name = path.name
        category = "公务员" if "公务员" in name or "考录职位" in name else "事业单位"
        city = next((city for city in ("苏州", "南京", "无锡", "南通", "常州", "扬州", "镇江", "徐州", "盐城", "泰州", "淮安", "宿迁", "连云港") if city in name), "江苏")
        jobs.extend(jobs_from_spreadsheet(path, {
            "category": category,
            "employment_status": "编内",
            "city": city,
            "source_name": f"本地历史资料：{name}",
            "source_url": "",
            "official": True,
            "published_at": "2026-01-01" if "2026" in name else "",
        }))
    return jobs

