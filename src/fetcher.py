"""
RSS Feed & Public API Fetcher for Personal AI News Aggregator.
Fetches real-time news from trusted sources (Reuters, BBC, CNBC, Bloomberg, The Guardian,
TechCrunch, MIT Tech Review, IEEE Spectrum, IEA, World Bank, Mining.com, OilPrice, CoinDesk, etc.)
with retry mechanisms, timeouts, URL validation, HTML sanitization, and deduplication.
"""
import hashlib
import html
import logging
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Set, Tuple
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import feedparser
import httpx
from bs4 import BeautifulSoup

from config.settings import (
    TRUSTED_FEEDS,
    HTTP_TIMEOUT_SECONDS,
    MAX_RETRIES,
    MAX_ARTICLES_PER_FEED,
    MAX_TOTAL_ARTICLES_PER_RUN,
    VERIFY_ARTICLE_URLS,
)
from src.models import RawArticle
from src.categorizer import is_relevant_article
from src.database import NewsDatabase

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36 PersonalAINewsIntelligence/1.0"
)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "rss"
}


def normalize_url(url: str) -> str:
    """Cleans tracking parameters and normalizes a URL for accurate deduplication."""
    if not url:
        return ""
    url = url.strip()
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        query_params = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        cleaned = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            query=urlencode(query_params),
            fragment="",
        )
        return urlunparse(cleaned)
    except Exception:
        return url


def clean_html_text(raw_html: str) -> str:
    """Removes HTML tags, scripts, and extra whitespace from RSS descriptions."""
    if not raw_html:
        return ""
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "img", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:1200]
    except Exception:
        cleaned = re.sub(r"<[^>]+>", " ", raw_html)
        return re.sub(r"\s+", " ", html.unescape(cleaned)).strip()[:1200]


def compute_hashes(url: str, title: str) -> Tuple[str, str]:
    """Computes SHA-256 hashes for normalized URL and normalized title."""
    norm_url = normalize_url(url)
    norm_title = re.sub(r"[^a-z0-9]+", "", title.lower())
    url_hash = hashlib.sha256(norm_url.encode("utf-8")).hexdigest()
    title_hash = hashlib.sha256(norm_title.encode("utf-8")).hexdigest()
    return url_hash, title_hash


def parse_publication_date(entry: Any) -> Tuple[str, str]:
    """Extracts (YYYY-MM-DD HH:MM:SS, YYYY-MM-DD) from feed entry or defaults to current time."""
    now = datetime.now()
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        struct_time = getattr(entry, attr, None) or (entry.get(attr) if isinstance(entry, dict) else None)
        if struct_time:
            try:
                dt = datetime(*struct_time[:6])
                return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    for str_attr in ("published", "updated", "pubDate", "lnchdt"):
        raw_date = getattr(entry, str_attr, None) or (entry.get(str_attr) if isinstance(entry, dict) else None)
        if raw_date and isinstance(raw_date, str):
            try:
                dt = parsedate_to_datetime(raw_date)
                return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")
            except Exception:
                try:
                    dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d %H:%M:%S"), dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

    return now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d")


class NewsFetcher:
    """Fetches, validates, and deduplicates news articles from configured RSS & API endpoints."""

    def __init__(self, db: NewsDatabase):
        self.db = db
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml, application/json, */*",
        }

    def _fetch_with_retry(self, client: httpx.Client, url: str) -> httpx.Response:
        """Fetches a URL with exponential backoff retry logic."""
        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.get(url, timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=True)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_exc = exc
                wait_time = 1.2 * attempt
                logger.warning(
                    "Fetch attempt %d/%d failed for %s: %s. Retrying in %.1fs...",
                    attempt, MAX_RETRIES, url, exc, wait_time
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait_time)
        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {last_exc}")

    def _parse_worldbank_api(
        self, payload: Dict[str, Any], feed_cfg: Dict[str, Any]
    ) -> List[RawArticle]:
        """Parses the official World Bank News JSON API response."""
        results: List[RawArticle] = []
        documents = payload.get("documents", {})
        if not isinstance(documents, dict):
            return results

        for doc_key, doc in documents.items():
            if doc_key == "facets" or not isinstance(doc, dict):
                continue
            title_val = doc.get("title", "")
            if isinstance(title_val, dict):
                title = title_val.get("cdata!", "") or next(iter(title_val.values()), "")
            else:
                title = str(title_val)
            title = clean_html_text(title)

            url = doc.get("url", "") or doc.get("guid", "")
            url = normalize_url(url)
            if not title or not url:
                continue

            desc_val = doc.get("descr", "") or doc.get("abstract", "")
            if isinstance(desc_val, dict):
                desc = desc_val.get("cdata!", "") or next(iter(desc_val.values()), "")
            else:
                desc = str(desc_val)
            desc = clean_html_text(desc) or f"Laporan resmi dan pembaruan kebijakan ekonomi global dari World Bank terkait {title}."

            pub_at, pub_date = parse_publication_date(doc)
            url_hash, title_hash = compute_hashes(url, title)

            results.append(
                RawArticle(
                    title=title,
                    source=feed_cfg["source_label"],
                    feed_name=feed_cfg["name"],
                    url=url,
                    published_at=pub_at,
                    published_date=pub_date,
                    description=desc,
                    default_category=feed_cfg["default_category"],
                    url_hash=url_hash,
                    title_hash=title_hash,
                    url_verified=True,
                )
            )
            if len(results) >= MAX_ARTICLES_PER_FEED:
                break
        return results

    def _parse_rss_feed(self, content: bytes, feed_cfg: Dict[str, Any]) -> List[RawArticle]:
        """Parses standard RSS/Atom XML content using feedparser."""
        parsed = feedparser.parse(content)
        results: List[RawArticle] = []

        for entry in parsed.entries[: MAX_ARTICLES_PER_FEED * 2]:
            raw_title = getattr(entry, "title", "")
            title = clean_html_text(raw_title)
            raw_link = getattr(entry, "link", "")
            url = normalize_url(raw_link)

            if not title or not url:
                continue

            # Extract source label if Google News RSS aggregator format "Headline - Source"
            source_label = feed_cfg["source_label"]
            if " - " in title and "news.google.com" in feed_cfg["url"]:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2 and len(parts[1]) < 35:
                    title = parts[0].strip()
                    extracted_src = parts[1].strip()
                    if extracted_src:
                        source_label = extracted_src

            # Extract description / summary
            raw_desc = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or ""
            )
            if not raw_desc and hasattr(entry, "content") and entry.content:
                raw_desc = entry.content[0].get("value", "")

            desc = clean_html_text(raw_desc)
            # If Google News RSS repeats the title in description, provide clean metadata fallback
            if not desc or desc.lower().startswith(title.lower()[:40]):
                desc = f"Berita terbaru yang dilaporkan oleh {source_label} mengenai: {title}."

            pub_at, pub_date = parse_publication_date(entry)
            url_hash, title_hash = compute_hashes(url, title)

            results.append(
                RawArticle(
                    title=title,
                    source=source_label,
                    feed_name=feed_cfg["name"],
                    url=url,
                    published_at=pub_at,
                    published_date=pub_date,
                    description=desc,
                    default_category=feed_cfg["default_category"],
                    url_hash=url_hash,
                    title_hash=title_hash,
                    url_verified=True,
                )
            )
            if len(results) >= MAX_ARTICLES_PER_FEED:
                break

        return results

    def fetch_all(self, ignore_db_duplicates: bool = False) -> Tuple[List[RawArticle], Dict[str, int]]:
        """
        Fetches articles across all configured feeds, filters duplicates & irrelevant items,
        and returns (new_articles, stats_dict).
        """
        collected: List[RawArticle] = []
        seen_url_hashes: Set[str] = set()
        seen_title_hashes: Set[str] = set()

        stats = {
            "feeds_checked": 0,
            "feeds_succeeded": 0,
            "feeds_failed": 0,
            "raw_fetched": 0,
            "duplicates_skipped": 0,
            "irrelevant_skipped": 0,
            "accepted": 0,
        }

        with httpx.Client(headers=self.headers, verify=True) as client:
            for feed_cfg in TRUSTED_FEEDS:
                stats["feeds_checked"] += 1
                feed_name = feed_cfg["name"]
                feed_url = feed_cfg["url"]
                feed_type = feed_cfg.get("type", "rss")

                try:
                    logger.info("Fetching feed [%s]: %s", feed_name, feed_url)
                    resp = self._fetch_with_retry(client, feed_url)
                    if feed_type == "worldbank_api":
                        feed_articles = self._parse_worldbank_api(resp.json(), feed_cfg)
                    else:
                        feed_articles = self._parse_rss_feed(resp.content, feed_cfg)

                    stats["feeds_succeeded"] += 1
                    stats["raw_fetched"] += len(feed_articles)
                    logger.info(
                        "Successfully parsed %d items from %s", len(feed_articles), feed_name
                    )

                    for item in feed_articles:
                        # 1. Check in-memory session duplicates
                        if item.url_hash in seen_url_hashes or item.title_hash in seen_title_hashes:
                            stats["duplicates_skipped"] += 1
                            continue

                        # 2. Check SQLite database duplicates
                        if not ignore_db_duplicates and self.db.is_duplicate(item.url_hash, item.title_hash):
                            stats["duplicates_skipped"] += 1
                            continue

                        # 3. Check relevance & URL validity
                        if not is_relevant_article(item):
                            stats["irrelevant_skipped"] += 1
                            continue

                        seen_url_hashes.add(item.url_hash)
                        seen_title_hashes.add(item.title_hash)
                        collected.append(item)
                        stats["accepted"] += 1

                except Exception as exc:
                    stats["feeds_failed"] += 1
                    logger.error("Failed to fetch feed [%s]: %s", feed_name, exc)

        # Balance across categories so no single feed dominates and limit to MAX_TOTAL_ARTICLES_PER_RUN
        if len(collected) > MAX_TOTAL_ARTICLES_PER_RUN:
            collected = self._balance_selection(collected, MAX_TOTAL_ARTICLES_PER_RUN)
            stats["accepted"] = len(collected)

        return collected, stats

    @staticmethod
    def _balance_selection(articles: List[RawArticle], max_count: int) -> List[RawArticle]:
        """Selects articles round-robin across default categories to ensure diverse coverage."""
        by_cat: Dict[str, List[RawArticle]] = {}
        for art in articles:
            by_cat.setdefault(art.default_category, []).append(art)

        balanced: List[RawArticle] = []
        while len(balanced) < max_count and any(by_cat.values()):
            for cat in list(by_cat.keys()):
                if by_cat[cat] and len(balanced) < max_count:
                    balanced.append(by_cat[cat].pop(0))
        return balanced

