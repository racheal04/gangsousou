from gangsousou.matcher import assess
from gangsousou.models import Job


PROFILE = {
    "graduation_year": 2028,
    "degree_level": "硕士研究生",
    "major_terms": ["资源与环境", "085700", "测绘", "遥感", "专业不限"],
    "city_priority": ["苏州", "南京", "无锡"],
    "category_priority": ["公务员", "选调生", "参公", "事业单位", "军队文职", "国企正式岗", "身份待核实"],
    "exclude_dispatch": True,
    "exclude_physical_test": True,
    "has_student_cadre_experience": False,
    "has_school_level_award": False,
}


def test_high_match_resource_environment_position():
    job = Job(id="1", title="苏州市公务员招录", position="测绘管理", category="公务员", city="苏州", education="研究生", majors="资源与环境（085700）、测绘科学与技术", employment_status="编内")
    result = assess(job, PROFILE)
    assert result.section == "可报名"
    assert result.match["level"] == "高把握"
    assert result.match["score"] >= 80


def test_dispatch_is_excluded():
    job = Job(id="2", title="劳务派遣人员招聘", category="身份待核实", summary="采用劳务派遣用工")
    result = assess(job, PROFILE)
    assert result.match["level"] == "不符合"
    assert result.section == "趋势参考"


def test_other_graduation_year_is_reference():
    job = Job(id="3", title="2026年毕业生招聘", target_group="2026年应届毕业生", majors="专业不限")
    result = assess(job, PROFILE)
    assert result.match["level"] == "不符合"
    assert any("非2028届" in reason for reason in result.match["blockers"])


def test_uncertain_employment_goes_to_identity_section():
    job = Job(id="4", title="国企校园招聘", category="身份待核实", employment_status="待核实", majors="专业不限")
    result = assess(job, PROFILE)
    assert result.section == "身份待核实"


def test_old_recruitment_cycle_is_reference_for_2028_student():
    job = Job(id="5", title="事业单位公开招聘", category="事业单位", published_at="2026-08-01", majors="资源与环境")
    result = assess(job, PROFILE)
    assert result.section == "趋势参考"
    assert any("早于2028届" in reason for reason in result.match["blockers"])


def test_male_only_position_is_excluded():
    profile = {**PROFILE, "gender": "女"}
    job = Job(id="6", title="公务员招录", category="公务员", other_requirements="限男性", majors="专业不限")
    result = assess(job, profile)
    assert result.match["level"] == "不符合"
