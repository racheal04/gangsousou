from __future__ import annotations

import os
from html import escape

import requests

from .models import Job


def pushplus_digest(new_jobs: list[Job], site_url: str) -> bool:
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token or not new_jobs:
        return False
    ranked = sorted(
        (job for job in new_jobs if job.match.get("level") != "不符合" and job.official),
        key=lambda job: job.match.get("score", 0),
        reverse=True,
    )[:10]
    if not ranked:
        return False
    rows = []
    for index, job in enumerate(ranked, 1):
        rows.append(
            f"<p><b>{index}. {escape(job.title)}</b><br>"
            f"{escape(job.city)} · {escape(job.category)} · 匹配 {job.match.get('score', 0)} 分<br>"
            f"<a href=\"{escape(job.source_url)}\">查看官方公告</a></p>"
        )
    content = "".join(rows) + f'<p><a href="{escape(site_url)}">打开岗搜搜查看全部岗位</a></p>'
    response = requests.post(
        "https://www.pushplus.plus/send",
        json={"token": token, "title": f"岗搜搜：今日新增 {len(new_jobs)} 条", "content": content, "template": "html"},
        timeout=20,
    )
    response.raise_for_status()
    return bool(response.json().get("code") == 200)

