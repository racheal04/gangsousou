from pathlib import Path

import openpyxl

from gangsousou.attachments import jobs_from_spreadsheet


def test_xlsx_position_table_parsing(tmp_path: Path):
    path = tmp_path / "positions.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["招聘单位", "岗位代码", "岗位名称", "招聘对象", "专业", "学历", "其他条件和说明"])
    sheet.append(["某资源中心", "01", "遥感监测", "2028年毕业生", "资源与环境（085700）", "研究生", "中共党员"])
    book.save(path)
    jobs = jobs_from_spreadsheet(path, {"category": "事业单位", "city": "南京", "source_name": "测试", "source_url": "https://example.gov.cn/a"})
    assert len(jobs) == 1
    assert jobs[0].organization == "某资源中心"
    assert jobs[0].majors == "资源与环境（085700）"

