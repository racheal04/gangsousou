from __future__ import annotations

import os
from html import escape

import requests

from .models import Job


def _status_text(value) -> str:
    if isinstance(value, dict):
        for key in ("status", "statusDesc", "message", "msg"):
            if value.get(key) not in (None, ""):
                return str(value[key])
    if isinstance(value, str):
        return value
    return ""


def wxpusher_digest(jobs: list[Job], site_url: str, new_count: int = 0) -> str:
    app_token = os.getenv("WXPUSHER_APP_TOKEN", "").strip()
    uid = os.getenv("WXPUSHER_UID", "").strip()
    if not app_token or not uid:
        return ""
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
        "https://wxpusher.zjiecode.com/api/send/message",
        json={
            "appToken": app_token,
            "uids": [uid],
            "summary": title,
            "content": content,
            "contentType": 2,
            "url": site_url,
        },
        timeout=20,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("code") != 1000 or result.get("success") is False:
        raise RuntimeError(result.get("msg") or f"WxPusher 返回代码 {result.get('code')}")
    records = result.get("data") or []
    if not records:
        raise RuntimeError("WxPusher 未返回发送记录")
    record = records[0]
    if record.get("code") != 1000:
        raise RuntimeError(record.get("status") or "WxPusher 未创建发送任务")
    status = _status_text(record) or "已创建发送任务"
    send_record_id = record.get("sendRecordId")
    if send_record_id:
        try:
            status_response = requests.get(
                "https://wxpusher.zjiecode.com/api/send/query/status",
                params={"sendRecordId": send_record_id},
                timeout=20,
            )
            status_response.raise_for_status()
            status_result = status_response.json()
            if status_result.get("code") == 1000:
                status = _status_text(status_result.get("data")) or status
        except requests.RequestException:
            pass
    return status
