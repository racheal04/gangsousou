from __future__ import annotations

import os
from html import escape

import requests

from .models import Job


def pushplus_digest(jobs: list[Job], site_url: str, new_count: int = 0) -> bool:
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    if not token:
        return False
    ranked = sorted(
        (job for job in jobs if job.match.get("level") != "不符合" and job.official),
        key=lambda job: (
            job.section == "可报名",
            job.match.get("score", 0),
            job.published_at,
        ),
        reverse=True,
    )[:10]
    rows = []
    for index, job in enumerate(ranked, 1):
        rows.append(
            f"<p><b>{index}. {escape(job.title)}</b><br>"
            f"{escape(job.city)} · {escape(job.category)} · 匹配 {job.match.get('score', 0)} 分<br>"
            f"<a href=\"{escape(job.source_url)}\">查看官方公告</a></p>"
        )
    if ranked:
        title = f"岗搜搜：今日新增 {new_count} 条｜精选 {len(ranked)} 个"
        content = "".join(rows)
    else:
        trend_count = sum(job.section == "趋势参考" for job in jobs)
        title = "岗搜搜：今日暂无可报名岗位"
        content = f"<p>今日暂未发现符合当前身份条件的可报名岗位。</p><p>岗位库中有 {trend_count} 条趋势参考记录。</p>"
    content += f'<p><a href="{escape(site_url)}">打开岗搜搜查看全部岗位</a></p>'
    response = requests.post(
        "https://www.pushplus.plus/send",
        json={
            "token": token,
            "title": title,
            "content": content,
            "template": "html",
        },
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 200:
        raise RuntimeError(result.get("msg") or f"PushPlus 返回代码 {result.get('code')}")
    return True
