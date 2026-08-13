from __future__ import annotations

import re
from datetime import date

from .models import Job
from .text import clean, is_expired


IDENTITY_UNCERTAIN = ("备案制", "人员控制总量", "合同制", "劳务合同", "用工性质未明确")
DISPATCH_TERMS = ("劳务派遣", "人才派遣", "编外", "外包用工", "劳务用工")
PHYSICAL_TERMS = ("体能测评", "体能测试", "体测")
MAJOR_SEPARATORS = re.compile(r"[，,、；;。\n\r|]+")


def _contains_any(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def _city_score(city: str, profile: dict) -> int:
    for index, preferred in enumerate(profile.get("city_priority", [])):
        if preferred in city:
            return max(0, 15 - index)
    return 1 if city == "江苏" else 0


def _category_score(category: str, profile: dict) -> int:
    priorities = profile.get("category_priority", [])
    try:
        return max(0, 18 - priorities.index(category) * 2)
    except ValueError:
        return 0


def _major_tokens(majors: str) -> list[str]:
    """Split a major requirement into formal entries without substring matching."""
    return [clean(token).replace(" ", "") for token in MAJOR_SEPARATORS.split(majors) if clean(token)]


def _major_name(token: str) -> str:
    """Remove a standalone six-digit major code while preserving the major name."""
    return re.sub(r"[（(]?\b\d{6}\b[）)]?", "", token).strip(" ：:（）()")


def _assess_major(job: Job, profile: dict, reasons: list[str], warnings: list[str]) -> int:
    majors = clean(job.majors)
    if not majors:
        warnings.append("公告页未提取到具体专业，需查看职位表附件")
        return 0

    tokens = _major_tokens(majors)
    names = set(profile.get("major_exact_names", [profile.get("major", "资源与环境")]))
    codes = set(profile.get("major_codes", [profile.get("major_code", "085700")]))
    normalized_names = {_major_name(token) for token in tokens}
    matched_names = sorted(name for name in names if name and name in normalized_names)
    matched_codes = sorted(code for code in codes if code and re.search(rf"(?<!\d){re.escape(code)}(?!\d)", majors))

    if matched_names or matched_codes:
        label = "、".join([*matched_names, *matched_codes])
        reasons.append(f"专业精确命中：{label}")
        return 24

    if any(token in {"不限", "专业不限", "不限专业", "专业不作限制"} for token in tokens):
        reasons.append("专业不限")
        return 24

    catalog = profile.get("major_catalog", {})
    categories = set(catalog.get("graduate_categories", []))
    matched_categories = sorted(category for category in categories if category in normalized_names)
    if matched_categories:
        category_label = "、".join(matched_categories)
        catalog_name = catalog.get("name", "江苏公务员专业参考目录")
        if job.category in {"公务员", "参公", "选调生"}:
            reasons.append(f"专业大类命中：{category_label}（依据{catalog_name}）")
            return 24
        warnings.append(f"目录大类命中：{category_label}；需确认该公告采用{catalog_name}")
        return 10

    direction_terms = profile.get("research_direction_terms", [])
    matched_directions = sorted({term for term in direction_terms if term and any(term in token for token in tokens)})
    if matched_directions:
        warnings.append(f"仅研究方向相关：{'、'.join(matched_directions[:3])}；毕业证专业为资源与环境，需咨询招录单位")
        return 6

    warnings.append("未命中资源与环境（085700）或其江苏公务员目录大类")
    return -12


def assess(job: Job, profile: dict) -> Job:
    text = clean(" ".join([
        job.title, job.organization, job.position, job.majors, job.education,
        job.political_status, job.target_group, job.experience, job.other_requirements,
        job.summary,
    ]))
    blockers: list[str] = []
    warnings: list[str] = []
    reasons: list[str] = []
    score = 35 + _city_score(job.city, profile) + _category_score(job.category, profile)

    job.dispatch = job.dispatch or _contains_any(text, DISPATCH_TERMS)
    job.physical_test = job.physical_test or _contains_any(text, PHYSICAL_TERMS)
    if job.dispatch and profile.get("exclude_dispatch", True):
        blockers.append("属于劳务派遣、编外或外包用工")
    if job.physical_test and profile.get("exclude_physical_test", True):
        blockers.append("岗位要求体能测试")
    if _contains_any(text, ("异地驻点", "长期驻点", "驻外工作", "需驻外")):
        blockers.append("岗位包含异地或长期驻点要求")
    if profile.get("gender") == "女" and re.search(r"(?:仅限|限|适合)?男(?:性)?", text) and not re.search(r"女(?:性)?", text):
        blockers.append("岗位限男性或明确更适合男性")
    if profile.get("gender") == "女" and re.search(r"(?:仅限|限)女(?:性)?", text):
        reasons.append("女性岗位条件符合")

    if is_expired(job.deadline):
        blockers.append("报名已经截止")

    graduation_year = int(profile.get("graduation_year", 2028))
    mentioned_years = {int(y) for y in re.findall(r"(20\d{2})年(?:度|毕业生|应届)?", text)}
    candidate_years = {y for y in mentioned_years if 2024 <= y <= 2032}
    published_year = 0
    try:
        published_year = int((job.published_at or "")[:4])
    except ValueError:
        pass
    if published_year and published_year <= graduation_year - 2 and graduation_year not in candidate_years:
        blockers.append(f"招聘周期早于{graduation_year}届，当前仅作趋势参考")
    if candidate_years and graduation_year not in candidate_years and (
        "毕业生" in text or "应届" in text or "校招" in text
    ):
        blockers.append(f"公告面向{','.join(map(str, sorted(candidate_years)))}届/年度，非2028届")

    if "研究生" in job.education or "硕士" in job.education or "研究生" in text:
        score += 8
        reasons.append("学历条件包含研究生")
    elif job.education and any(x in job.education for x in ("专科", "本科")) and "以上" not in job.education:
        warnings.append("学历口径需要核对是否接受硕士以研究生身份报考")

    score += _assess_major(job, profile, reasons, warnings)

    if "中共党员" in text or "党员" in text:
        score += 7
        reasons.append("党员条件符合")
    if "六级" in text or "CET-6" in text.upper():
        score += 4
        reasons.append("已具备英语六级成绩")
    if "基层工作经历" in text or re.search(r"\d+年(?:以上)?工作经历", text):
        warnings.append("可能要求基层或相关工作经历")
        score -= 10
    if "学生干部" in text and not profile.get("has_student_cadre_experience"):
        blockers.append("要求学生干部经历")
    if ("校级以上" in text and ("奖励" in text or "荣誉" in text)) and not profile.get("has_school_level_award"):
        blockers.append("要求校级以上奖励或荣誉")

    if _contains_any(text, IDENTITY_UNCERTAIN) or job.employment_status == "待核实":
        warnings.append("编制或正式用工身份需要向招聘单位确认")

    if job.category in {"公务员", "选调生", "参公"}:
        reasons.append("行政编制方向优先")
    if job.city in profile.get("city_priority", [])[:5]:
        reasons.append(f"地点优先：{job.city}")

    score = max(0, min(100, score))
    if blockers:
        level = "不符合"
        section = "趋势参考"
    elif warnings:
        level = "待确认"
        section = "身份待核实" if any("编制或正式用工" in w for w in warnings) else "可报名"
    else:
        level = "高把握"
        section = "可报名"

    if job.published_at:
        try:
            if int(job.published_at[:4]) < date.today().year:
                section = "趋势参考"
        except ValueError:
            pass

    job.match = {
        "level": level,
        "score": score,
        "reasons": reasons[:8],
        "warnings": warnings[:8],
        "blockers": blockers[:8],
    }
    job.section = section
    return job
