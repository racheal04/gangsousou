# 岗搜搜

岗搜搜是一套只为个人使用的江苏编制与国企正式岗位情报台。它每天从配置的官方网页发现招聘公告，解析公告和职位表附件，依据个人条件给出“高把握 / 待确认 / 不符合”三档结果，并生成可由 GitHub Pages 免费托管的网页。

## 第一版能力

- 收录公务员、参公、选调生、事业单位、军队文职、国企正式岗与身份待核实岗位。
- 支持 HTML 公告和 `.xls`、`.xlsx`、`.csv`、`.pdf`、`.docx` 附件的基础解析。
- 按 2028 届、资源与环境（085700）、测绘与遥感方向、党员、英语成绩和城市偏好评分。
- 自动排除体能测试、劳务派遣、编外和人才派遣。
- 网页支持筛选、收藏和“准备报名 / 已报名 / 已放弃”状态；个人操作保存在本机浏览器。
- GitHub Actions 每天北京时间 20:00 左右运行，并通过 WxPusher 推送前 10 个高匹配岗位；没有可报名岗位时也会发送状态提醒。
- 历史岗位永久保存在 `data/jobs.json`。
- 首批来源覆盖江苏省级公务员/事业单位栏目、13个设区市人社官网、江苏省国资委和军队人才网。

## 重要边界

匹配结果是信息筛选工具，不是招录单位的资格审查结论。遇到“相关专业”、专业目录口径、备案制、合同制或未明确正式用工的岗位，系统会标记为“待确认”或“身份待核实”。报名前必须打开官方公告和职位表复核。

网站改版、验证码、访问频率限制和仅在微信公众号发布的信息，可能导致自动采集遗漏。运行状态会显示在网页底部。

## 本地运行

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest
$env:PYTHONPATH="src"
python -m gangsousou --no-push
pytest -q
python -m http.server 8000
```

浏览器打开 `http://localhost:8000`。

导入项目上一级目录中的历史职位表：

```powershell
$env:PYTHONPATH="src"
python -m gangsousou --import-local ".." --local-only --no-push
```

## GitHub 部署概要

1. 创建一个公开 GitHub 仓库，把本项目推送到仓库。
2. 在仓库 `Settings → Pages` 中选择 `GitHub Actions` 作为发布来源。
3. 微信扫描 WxPusher 极简推送二维码并获取个人 SPT。
4. 在 `Settings → Secrets and variables → Actions` 新建 Secret：`WXPUSHER_SPT`。
5. 在同一页面新建 Variable：`SITE_URL`，值为 GitHub Pages 网站地址。
6. 打开 `Actions → 每日采集与发布 → Run workflow` 做首次手动测试。

`WXPUSHER_SPT` 只能存放在 GitHub Secret 中，不要写进代码、截图或聊天记录。

定时表达式使用 UTC 12:00，对应北京时间 20:00。GitHub 的定时任务可能因排队延后几分钟。

## 增加信息源

编辑 `config/sources.json`，增加官方列表页、岗位类别、默认城市和允许的官方域名。系统只把允许域名内的链接标记为“官方来源”。不同网站结构差异较大；若通用发现器抓不到，可在 `src/gangsousou/crawler.py` 中增加专用适配规则。
