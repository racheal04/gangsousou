from gangsousou.matcher import assess
from gangsousou.models import Job


PROFILE = {
    "graduation_year": 2028,
    "degree_level": "硕士研究生",
    "major_exact_names": ["资源与环境"],
    "major_codes": ["085700"],
    "major_catalog": {
        "name": "江苏省2026年度考试录用公务员专业参考目录",
        "graduate_categories": ["土地管理类", "测绘类", "地质矿产类", "安全生产类", "环境保护类"],
    },
    "research_direction_terms": ["测绘", "遥感", "测绘工程", "遥感科学与技术"],
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


def test_resource_environment_economics_is_not_a_major_match():
    job = Job(
        id="7",
        title="一级主任科员以下",
        category="公务员",
        education="研究生",
        majors="国民经济学，产业经济学，人口、资源与环境经济学，审计学",
    )
    result = assess(job, PROFILE)
    assert not any("专业精确命中" in reason for reason in result.match["reasons"])
    assert any("未命中资源与环境" in warning for warning in result.match["warnings"])


def test_jiangsu_catalog_category_is_a_civil_service_match():
    job = Job(id="8", title="公务员招录", category="公务员", employment_status="编内", education="研究生", majors="测绘类")
    result = assess(job, PROFILE)
    assert any("专业大类命中：测绘类" in reason for reason in result.match["reasons"])
    assert result.match["level"] == "高把握"


def test_research_direction_is_not_treated_as_formal_major():
    job = Job(id="9", title="专业技术岗", category="事业单位", education="研究生", majors="测绘工程")
    result = assess(job, PROFILE)
    assert not any("专业精确命中" in reason for reason in result.match["reasons"])
    assert any("仅研究方向相关" in warning for warning in result.match["warnings"])
