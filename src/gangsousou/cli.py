from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path

from .crawler import Crawler
from .local_import import import_local_files
from .matcher import assess
from .notify import pushplus_digest
from .storage import load_jobs, merge_jobs, save_jobs


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(args: argparse.Namespace) -> int:
    root = project_root()
    profile = load_json(root / "config" / "profile.json")
    sources = load_json(root / "config" / "sources.json")
    data_path = root / "data" / "jobs.json"
    existing = {} if args.replace else load_jobs(data_path)
    incoming = []
    source_runs = []

    if args.import_local:
        local_jobs = import_local_files(Path(args.import_local))
        incoming.extend(local_jobs)
        source_runs.append({"source": "本地历史资料", "ok": True, "found": len(local_jobs), "error": ""})

    if not args.local_only:
        crawler = Crawler()
        selected = [source for source in sources if not args.source or source["id"] == args.source]
        for source in selected:
            jobs, result = crawler.crawl_source(source)
            incoming.extend(jobs)
            source_runs.append(result)

    assessed = [assess(job, profile) for job in incoming]
    merged, new_jobs = merge_jobs(existing, assessed)
    merged = {
        job_id: job for job_id, job in merged.items()
        if not (
            not job.position and not job.majors and not job.published_at and not re.search(r"20\d{2}", job.title)
            and ("index.html" in job.source_url or "tyzpwb" in job.source_url)
        )
    }
    new_jobs = [job for job in new_jobs if job.id in merged]
    for job in merged.values():
        assess(job, profile)
        if job.source_name.startswith("本地历史资料"):
            job.section = "趋势参考"
    save_jobs(data_path, merged, source_runs)
    if not args.no_push:
        try:
            pushplus_digest(new_jobs, os.getenv("SITE_URL", ""))
        except Exception as exc:
            logging.getLogger(__name__).error("微信推送失败：%s", exc)
    print(json.dumps({"total": len(merged), "incoming": len(incoming), "new": len(new_jobs), "sources": source_runs}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="岗搜搜每日采集与匹配")
    parser.add_argument("--source", help="只运行指定来源 ID")
    parser.add_argument("--import-local", help="导入本地 xls/xlsx 历史职位表目录")
    parser.add_argument("--local-only", action="store_true", help="只导入本地文件，不联网")
    parser.add_argument("--no-push", action="store_true", help="不发送微信推送")
    parser.add_argument("--replace", action="store_true", help="重建岗位库（用于重新导入历史样本）")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
