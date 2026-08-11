from gangsousou.models import Job
from gangsousou.notify import pushplus_digest


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 200, "msg": "success"}


def test_pushplus_sends_daily_digest_when_no_new_jobs(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("PUSHPLUS_TOKEN", "test-token")
    monkeypatch.setattr("gangsousou.notify.requests.post", fake_post)
    job = Job(
        id="job-1",
        title="测绘岗位",
        organization="某事业单位",
        category="事业单位",
        employment_status="编内",
        city="苏州",
        source_name="官方来源",
        source_url="https://example.gov.cn/job/1",
        official=True,
        section="趋势参考",
        match={"level": "较匹配", "score": 80},
    )

    assert pushplus_digest([job], "https://example.github.io/", new_count=0)
    assert captured["json"]["title"] == "岗搜搜：今日新增 0 条｜精选 1 个"
    assert "测绘岗位" in captured["json"]["content"]


def test_pushplus_sends_empty_status_when_only_trend_jobs_exist(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("PUSHPLUS_TOKEN", "test-token")
    monkeypatch.setattr("gangsousou.notify.requests.post", fake_post)
    job = Job(
        id="job-2",
        title="往年岗位",
        organization="某事业单位",
        category="事业单位",
        employment_status="编内",
        city="南京",
        source_name="官方来源",
        source_url="https://example.gov.cn/job/2",
        official=True,
        section="趋势参考",
        match={"level": "不符合", "score": 0},
    )

    assert pushplus_digest([job], "https://example.github.io/", new_count=0)
    assert captured["json"]["title"] == "岗搜搜：今日暂无可报名岗位"
    assert "1 条趋势参考记录" in captured["json"]["content"]
