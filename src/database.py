"""
SQLite Database Manager for Personal AI News Aggregator.
Handles storage of processed articles, deduplication checks, and automation run logs.
"""
import json
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Iterator

from config.settings import DATABASE_PATH
from src.models import ProcessedArticle, PotentialImpact

logger = logging.getLogger(__name__)


class NewsDatabase:
    """Manages SQLite persistence and deduplication for news articles."""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Creates the required tables and indexes if they do not exist."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    headline_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    feed_name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    published_at TEXT NOT NULL,
                    published_date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    raw_description TEXT,
                    summary_id TEXT NOT NULL,
                    core_issue TEXT NOT NULL,
                    why_it_matters TEXT NOT NULL,
                    verified_facts_json TEXT NOT NULL,
                    ai_interpretation TEXT NOT NULL,
                    potential_impact_json TEXT NOT NULL,
                    sentiment TEXT NOT NULL,
                    sentiment_score REAL DEFAULT 0.0,
                    sentiment_reason TEXT,
                    keywords_json TEXT NOT NULL,
                    ai_provider_used TEXT NOT NULL,
                    ai_status TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,
                    title_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_url_hash ON articles(url_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_articles_pub_date ON articles(published_date)"
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS run_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_started_at TEXT NOT NULL,
                    run_finished_at TEXT,
                    trigger_type TEXT NOT NULL,
                    feeds_checked INTEGER DEFAULT 0,
                    articles_fetched INTEGER DEFAULT 0,
                    duplicates_skipped INTEGER DEFAULT 0,
                    articles_processed INTEGER DEFAULT 0,
                    ai_provider TEXT,
                    output_file TEXT,
                    status TEXT NOT NULL,
                    error_details TEXT
                )
                """
            )
            conn.commit()

    def is_duplicate(self, url_hash: str, title_hash: str) -> bool:
        """Checks whether an article with the same URL hash or title hash already exists."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM articles WHERE url_hash = ? OR title_hash = ? LIMIT 1",
                (url_hash, title_hash),
            )
            return cursor.fetchone() is not None

    def save_article(self, article: ProcessedArticle) -> Optional[int]:
        """Inserts a processed article into SQLite. Ignores if duplicate."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        article.created_at = now_str
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO articles (
                        title, headline_id, source, feed_name, url,
                        published_at, published_date, category, raw_description,
                        summary_id, core_issue, why_it_matters, verified_facts_json,
                        ai_interpretation, potential_impact_json, sentiment,
                        sentiment_score, sentiment_reason, keywords_json,
                        ai_provider_used, ai_status, url_hash, title_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.title,
                        article.headline_id,
                        article.source,
                        article.feed_name,
                        article.url,
                        article.published_at,
                        article.published_date,
                        article.category,
                        article.raw_description,
                        article.summary_id,
                        article.core_issue,
                        article.why_it_matters,
                        json.dumps(article.verified_facts, ensure_ascii=False),
                        article.ai_interpretation,
                        json.dumps(article.potential_impact.to_dict(), ensure_ascii=False),
                        article.sentiment,
                        article.sentiment_score,
                        article.sentiment_reason,
                        json.dumps(article.keywords, ensure_ascii=False),
                        article.ai_provider_used,
                        article.ai_status,
                        article.url_hash,
                        article.title_hash,
                        now_str,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logger.error("Database error saving article '%s': %s", article.title, exc)
            return None

    def get_recent_articles(self, limit: int = 60) -> List[ProcessedArticle]:
        """Fetches recent processed articles ordered by published_at DESC."""
        articles: List[ProcessedArticle] = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM articles
                ORDER BY published_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            for row in rows:
                impact_dict = json.loads(row["potential_impact_json"] or "{}")
                impact = PotentialImpact(
                    economy=impact_dict.get("economy", "-"),
                    technology=impact_dict.get("technology", "-"),
                    industry=impact_dict.get("industry", "-"),
                    society=impact_dict.get("society", "-"),
                )
                articles.append(
                    ProcessedArticle(
                        id=row["id"],
                        title=row["title"],
                        headline_id=row["headline_id"],
                        source=row["source"],
                        feed_name=row["feed_name"],
                        url=row["url"],
                        published_at=row["published_at"],
                        published_date=row["published_date"],
                        category=row["category"],
                        raw_description=row["raw_description"] or "",
                        summary_id=row["summary_id"],
                        core_issue=row["core_issue"],
                        why_it_matters=row["why_it_matters"],
                        verified_facts=json.loads(row["verified_facts_json"] or "[]"),
                        ai_interpretation=row["ai_interpretation"],
                        potential_impact=impact,
                        sentiment=row["sentiment"],
                        sentiment_score=float(row["sentiment_score"] or 0.0),
                        sentiment_reason=row["sentiment_reason"] or "",
                        keywords=json.loads(row["keywords_json"] or "[]"),
                        ai_provider_used=row["ai_provider_used"],
                        ai_status=row["ai_status"],
                        url_hash=row["url_hash"],
                        title_hash=row["title_hash"],
                        created_at=row["created_at"],
                    )
                )
        return articles

    def get_stats(self) -> Dict[str, Any]:
        """Returns aggregate statistics from the SQLite database."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM articles")
            total = cursor.fetchone()["total"]

            cursor.execute(
                "SELECT category, COUNT(*) as cnt FROM articles GROUP BY category"
            )
            by_cat = {r["category"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute(
                "SELECT sentiment, COUNT(*) as cnt FROM articles GROUP BY sentiment"
            )
            by_sent = {r["sentiment"]: r["cnt"] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(DISTINCT source) as src_cnt FROM articles")
            src_cnt = cursor.fetchone()["src_cnt"]

            return {
                "total_stored": total,
                "by_category": by_cat,
                "by_sentiment": by_sent,
                "distinct_sources": src_cnt,
            }

    def log_run_start(self, trigger_type: str = "MANUAL") -> int:
        """Creates a new execution log entry and returns its run ID."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO run_logs (run_started_at, trigger_type, status)
                VALUES (?, ?, ?)
                """,
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trigger_type, "RUNNING"),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def log_run_finish(
        self,
        run_id: int,
        feeds_checked: int,
        articles_fetched: int,
        duplicates_skipped: int,
        articles_processed: int,
        ai_provider: str,
        output_file: str,
        status: str = "SUCCESS",
        error_details: str = "",
    ) -> None:
        """Updates the run log entry upon completion."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE run_logs
                SET run_finished_at = ?,
                    feeds_checked = ?,
                    articles_fetched = ?,
                    duplicates_skipped = ?,
                    articles_processed = ?,
                    ai_provider = ?,
                    output_file = ?,
                    status = ?,
                    error_details = ?
                WHERE id = ?
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    feeds_checked,
                    articles_fetched,
                    duplicates_skipped,
                    articles_processed,
                    ai_provider,
                    output_file,
                    status,
                    error_details,
                    run_id,
                ),
            )
            conn.commit()
