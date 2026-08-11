from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from urllib.parse import urldefrag


RECRUIT_WORDS = (
    "招聘", "招录", "招考", "录用公务员", "选调", "文职人员", "校园招聘",
    "高校毕业生", "人才引进", "岗位计划", "招聘公告",
)
EXCLUDE_WORDS = (
    "拟录用", "拟聘用", "公示", "成绩", "资格复审", "面试名单", "体检名单",
    "取消岗位", "核减岗位", "补录结果", "录用名单", "考试大纲", "政策解读",
)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: str) -> str:
    value = "|".join(clean(part).lower() for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def canonical_url(url: str) -> str:
    return urldefrag(url.strip())[0]


def looks_like_recruitment(text: str) -> bool:
    text = clean(text)
    return any(word in text for word in RECRUIT_WORDS) and not any(word in text for word in EXCLUDE_WORDS)


def extract_date(text: str) -> str:
    patterns = [
        r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?",
        r"(20\d{2})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return date(*map(int, match.groups())).isoformat()
            except ValueError:
                pass
    return ""


def extract_deadline(text: str) -> str:
    candidates: list[str] = []
    for match in re.finditer(
        r"(?:网上报名|报名时间|报名申请|提交报名)[^。；\n]{0,100}?(?:至|截止|截至)[^。；\n]{0,30}?"
        r"(20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}日?)",
        text,
    ):
        parsed = extract_date(match.group(1))
        if parsed:
            candidates.append(parsed)
    return max(candidates) if candidates else ""


def is_expired(deadline: str) -> bool:
    if not deadline:
        return False
    try:
        return datetime.fromisoformat(deadline).date() < date.today()
    except ValueError:
        return False
