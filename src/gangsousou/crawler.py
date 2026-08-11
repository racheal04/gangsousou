from __future__ import annotations

import logging
import re
import tempfile
import time
import zipfile
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .attachments import jobs_from_spreadsheet, text_from_attachment
from .models import Job, now_iso
from .text import canonical_url, clean, extract_date, extract_deadline, looks_like_recruitment, stable_id

LOGGER = logging.getLogger(__name__)
ATTACHMENT_SUFFIXES = (".xls", ".xlsx", ".csv", ".pdf", ".docx", ".zip")


class Crawler:
    def __init__(self, timeout: int = 25):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 GangSouSou/0.1",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        retry = Retry(total=3, connect=3, read=2, status=2, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def fetch(self, url: str) -> requests.Response:
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return response

    def discover(self, source: dict) -> list[str]:
        response = self.fetch(source["url"])
        soup = BeautifulSoup(response.text, "html.parser")
        links: list[str] = []
        candidates = [
            (anchor.get("href", ""), clean(anchor.get_text(" ", strip=True) or anchor.get("title", "")))
            for anchor in soup.select("a[href]")
        ]
        for match in re.finditer(r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", response.text, re.I | re.S):
            raw_text = BeautifulSoup(unescape(match.group(2)), "html.parser").get_text(" ", strip=True)
            candidates.append((unescape(match.group(1)), clean(raw_text)))
        for raw_href, text in candidates:
            if not looks_like_recruitment(text):
                continue
            href = canonical_url(urljoin(response.url, raw_href))
            path = urlparse(href).path.lower()
            if href == canonical_url(response.url):
                continue
            if (path.endswith("/index.html") or path.endswith("/list.shtml") or path.endswith("/")) and not re.search(r"20\d{2}", text):
                continue
            if href.startswith("http") and href not in links:
                links.append(href)
        return links[: int(source.get("max_links", 40))]

    def parse_detail(self, url: str, source: dict) -> list[Job]:
        if any(ext in urlparse(url).path.lower() or ext in urlparse(url).query.lower() for ext in (".xls", ".xlsx", ".csv", ".zip")):
            return self._parse_direct_attachment(url, source)
        response = self.fetch(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        title = ""
        for title_node in soup.select("h1, .article-title, .xxgk_title, .title, title"):
            candidate = clean(title_node.get_text(" ", strip=True))
            if looks_like_recruitment(candidate):
                title = candidate
                break
        text = clean(soup.get_text("\n", strip=True))
        if not title or not looks_like_recruitment(title):
            return []
        published_at = extract_date(text[:1500]) or extract_date(url)
        deadline = extract_deadline(text)
        attachment_urls: list[str] = []
        for anchor in soup.select("a[href]"):
            href = canonical_url(urljoin(response.url, anchor.get("href", "")))
            label = clean(anchor.get_text(" ", strip=True))
            path = urlparse(href).path.lower()
            if path.endswith(ATTACHMENT_SUFFIXES) or "download" in href.lower() or "附件" in label:
                if href.startswith("http") and href not in attachment_urls:
                    attachment_urls.append(href)

        category = self._classify(title, text, source.get("category", "身份待核实"))
        employment_status = self._employment_status(title, text)
        if category == "事业单位" and employment_status == "待核实" and "事业单位公开招聘" in title:
            employment_status = "编内"
        base = Job(
            id=stable_id(url),
            title=title,
            category=category,
            employment_status=employment_status,
            city=self._city(title, text, source.get("city", "江苏")),
            source_name=source["name"],
            source_url=response.url,
            official=self._is_official(response.url, source),
            published_at=published_at,
            deadline=deadline,
            attachment_urls=attachment_urls,
            summary=text[:500],
            discovered_at=now_iso(),
            last_seen_at=now_iso(),
        )

        detailed: list[Job] = []
        with tempfile.TemporaryDirectory(prefix="gangsousou-") as tmp:
            for attachment_url in attachment_urls[:8]:
                try:
                    attachment = self._download(attachment_url, Path(tmp))
                    if attachment.suffix.lower() in {".xls", ".xlsx", ".csv"}:
                        detailed.extend(jobs_from_spreadsheet(attachment, {
                            **base.to_dict(),
                            "source_url": response.url,
                            "attachment_urls": attachment_urls,
                        }))
                    elif attachment.suffix.lower() in {".pdf", ".docx"}:
                        attachment_text = text_from_attachment(attachment)
                        if attachment_text:
                            base.summary = clean(f"{base.summary} {attachment_text[:2000]}")
                except Exception as exc:  # 单个附件失败不应拖垮整次采集
                    LOGGER.warning("附件解析失败 %s: %s", attachment_url, exc)
        return detailed or [base]

    def _parse_direct_attachment(self, url: str, source: dict) -> list[Job]:
        jobs: list[Job] = []
        with tempfile.TemporaryDirectory(prefix="gangsousou-direct-") as tmp:
            directory = Path(tmp)
            attachment = self._download(url, directory)
            files = [attachment]
            if attachment.suffix.lower() == ".zip":
                files = []
                with zipfile.ZipFile(attachment) as archive:
                    for member in archive.infolist():
                        suffix = Path(member.filename).suffix.lower()
                        if member.is_dir() or suffix not in {".xls", ".xlsx", ".csv"} or member.file_size > 30_000_000:
                            continue
                        target = directory / f"{stable_id(member.filename)}{suffix}"
                        target.write_bytes(archive.read(member))
                        files.append(target)
            for path in files:
                if path.suffix.lower() in {".xls", ".xlsx", ".csv"}:
                    jobs.extend(jobs_from_spreadsheet(path, {
                        "category": source.get("category", "身份待核实"),
                        "employment_status": "编内" if source.get("category") in {"公务员", "事业单位", "参公"} else "待核实",
                        "city": source.get("city", "江苏"),
                        "source_name": source["name"],
                        "source_url": url,
                        "official": self._is_official(url, source),
                        "attachment_urls": [url],
                    }))
        return jobs

    def crawl_source(self, source: dict) -> tuple[list[Job], dict]:
        result = {"source": source["name"], "url": source["url"], "ok": True, "found": 0, "error": ""}
        try:
            urls = self.discover(source)
            jobs: list[Job] = []
            for url in urls:
                try:
                    jobs.extend(self.parse_detail(url, source))
                    time.sleep(0.25)
                except Exception as exc:
                    LOGGER.warning("详情抓取失败 %s: %s", url, exc)
            result["found"] = len(jobs)
            return jobs, result
        except Exception as exc:
            result.update(ok=False, error=str(exc)[:300])
            LOGGER.error("来源抓取失败 %s: %s", source["name"], exc)
            return [], result

    def _download(self, url: str, directory: Path) -> Path:
        response = self.fetch(url)
        suffix = Path(urlparse(response.url).path).suffix.lower()
        content_type = response.headers.get("content-type", "").lower()
        if suffix not in ATTACHMENT_SUFFIXES:
            disposition = response.headers.get("content-disposition", "")
            extension_match = re.search(r"\.(xlsx?|csv|pdf|docx|zip)(?:[\"';?&]|$)", f"{url} {disposition}", re.I)
            if extension_match:
                suffix = f".{extension_match.group(1).lower()}"
            guesses = {
                "spreadsheetml": ".xlsx", "ms-excel": ".xls", "pdf": ".pdf",
                "wordprocessingml": ".docx", "zip": ".zip",
            }
            if suffix not in ATTACHMENT_SUFFIXES:
                suffix = next((ext for key, ext in guesses.items() if key in content_type), ".bin")
        path = directory / f"{stable_id(url)}{suffix}"
        path.write_bytes(response.content)
        return path

    @staticmethod
    def _is_official(url: str, source: dict) -> bool:
        host = urlparse(url).hostname or ""
        return any(host == domain or host.endswith(f".{domain}") for domain in source.get("official_domains", []))

    @staticmethod
    def _classify(title: str, text: str, fallback: str) -> str:
        sample = f"{title} {text[:1500]}"
        if "选调" in title:
            return "选调生"
        if "文职" in title and "军队" in sample:
            return "军队文职"
        if "事业单位" in title or "事业编制" in title:
            return "事业单位"
        if "公务员" in title or ("录用" in title and "考试" in title):
            return "公务员"
        if "参照公务员法管理" in title or "参公" in title:
            return "参公"
        if "事业单位" in sample or "事业编制" in sample:
            return "事业单位"
        if "国有企业" in sample or "国企" in sample or "央企" in sample:
            return "国企正式岗" if "正式" in sample else "身份待核实"
        return fallback

    @staticmethod
    def _employment_status(title: str, text: str) -> str:
        sample = f"{title} {text[:2000]}"
        if any(term in sample for term in ("劳务派遣", "编外", "人才派遣", "外包")):
            return "排除"
        if any(term in sample for term in ("备案制", "人员控制总量", "合同制")):
            return "待核实"
        if any(term in sample for term in ("事业编制", "纳入编制", "公务员", "参公", "军队文职")):
            return "编内"
        if "正式用工" in sample or "正式员工" in sample:
            return "正式用工"
        return "待核实"

    @staticmethod
    def _city(title: str, text: str, fallback: str) -> str:
        sample = f"{title} {text[:500]}"
        cities = ("苏州", "南京", "无锡", "南通", "常州", "扬州", "镇江", "徐州", "盐城", "泰州", "淮安", "宿迁", "连云港")
        return next((city for city in cities if city in sample), fallback)
