from gangsousou.crawler import Crawler


def test_title_driven_classification_ignores_navigation_noise():
    text = "导航：公务员考试专题；军队人才网；通知公告"
    assert Crawler._classify("苏州市事业单位公开招聘工作人员公告", text, "身份待核实") == "事业单位"
