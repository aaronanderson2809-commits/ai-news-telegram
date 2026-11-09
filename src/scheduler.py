"""
Automation Workflow & APScheduler Manager for Personal AI News Aggregator.
Coordinates the 8-stage pipeline:
1. Trigger -> 2. Fetch -> 3. Filter -> 4. Categorize -> 5. AI Processing -> 6. Generate HTML -> 7. Save -> 8. Logging
"""
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config.settings import SCHEDULE_INTERVAL_HOURS, DAILY_NOTIFICATION_TIME, RUN_ON_STARTUP
from src.database import NewsDatabase
from src.fetcher import NewsFetcher
from src.ai_engine import AIEngine
from src.report_generator import ReportGenerator
from src.email_notifier import send_crucial_gmail_digest
from src.models import ProcessedArticle

logger = logging.getLogger(__name__)


def send_desktop_notification(title: str, message: str) -> None:
    """Sends a native Windows desktop balloon/toast notification when a report is ready."""
    if sys.platform != "win32":
        return
    try:
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.BalloonTipIcon = 'Info'; "
            f"$n.BalloonTipTitle = '{title.replace(chr(39), '')}'; "
            f"$n.BalloonTipText = '{message.replace(chr(39), '')}'; "
            "$n.Visible = $True; "
            "$n.ShowBalloonTip(6000); "
            "Start-Sleep -Seconds 6; "
            "$n.Dispose()"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.debug("Could not display Windows desktop notification: %s", exc)


class NewsAggregationWorkflow:
    """Executes the end-to-end news intelligence pipeline safely and idempotently."""

    def __init__(self) -> None:
        self.db = NewsDatabase()
        self.fetcher = NewsFetcher(self.db)
        self.ai_engine = AIEngine()
        self.report_gen = ReportGenerator()

    def execute_pipeline(
        self,
        trigger_type: str = "MANUAL",
        force_refresh: bool = False,
        report_article_limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Runs the complete 8-stage aggregation workflow.
        Never re-processes existing articles unless `force_refresh=True`.
        """
        logger.info("=== [STAGE 1: TRIGGER] Starting News Aggregation Pipeline (trigger=%s) ===", trigger_type)
        run_id = self.db.log_run_start(trigger_type=trigger_type)

        try:
            # STAGE 2 & 3: FETCH & FILTER DUPLICATES/IRRELEVANT
            logger.info("=== [STAGE 2 & 3: FETCH & FILTER] Fetching RSS Feeds & Public APIs ===")
            new_raw_articles, fetch_stats = self.fetcher.fetch_all(ignore_db_duplicates=force_refresh)
            logger.info(
                "Fetch summary: feeds_checked=%d, raw_fetched=%d, duplicates_skipped=%d, new_accepted=%d",
                fetch_stats["feeds_checked"],
                fetch_stats["raw_fetched"],
                fetch_stats["duplicates_skipped"],
                fetch_stats["accepted"],
            )

            # STAGE 4 & 5: CATEGORIZE & AI PROCESSING (only for new articles!)
            logger.info(
                "=== [STAGE 4 & 5: CATEGORIZE & AI PROCESSING] Processing %d new articles via %s ===",
                len(new_raw_articles),
                self.ai_engine.active_engine_label,
            )
            newly_processed = self.ai_engine.analyze_articles_batch(new_raw_articles, batch_size=7)
            for processed_art in newly_processed:
                row_id = self.db.save_article(processed_art)
                if row_id:
                    processed_art.id = row_id

            # Retrieve combined recent articles from SQLite so idempotent re-runs still produce a full report
            report_articles = self.db.get_recent_articles(limit=report_article_limit)
            if not report_articles and newly_processed:
                report_articles = newly_processed

            # Generate Executive Summary & Closing Insights
            logger.info("=== [STAGE 5B: EXECUTIVE SUMMARY] Synthesizing macro intelligence ===")
            exec_summary = self.ai_engine.generate_executive_summary(report_articles)

            # STAGE 6 & 7: GENERATE HTML, GMAIL DIGEST & SAVE TO OUTPUT
            logger.info("=== [STAGE 6 & 7: GENERATE & SAVE HTML] Rendering HTML5 Editorial Report ===")
            db_stats = self.db.get_stats()
            paths = self.report_gen.generate_html_report(
                articles=report_articles,
                exec_summary=exec_summary,
                db_stats=db_stats,
            )

            # STAGE 7B: SEND CRUCIAL NEWS DIGEST TO GMAIL
            gmail_status = send_crucial_gmail_digest(
                articles=report_articles,
                exec_summary=exec_summary,
            )

            # STAGE 8: LOGGING
            self.db.log_run_finish(
                run_id=run_id,
                feeds_checked=fetch_stats["feeds_checked"],
                articles_fetched=fetch_stats["raw_fetched"],
                duplicates_skipped=fetch_stats["duplicates_skipped"],
                articles_processed=len(newly_processed),
                ai_provider=self.ai_engine.active_engine_label,
                output_file=str(paths["dated_path"]),
                status="SUCCESS",
            )

            logger.info(
                "=== [STAGE 8: COMPLETED] Newly processed=%d, Total in report=%d, Saved to %s ===",
                len(newly_processed),
                len(report_articles),
                paths["dated_path"],
            )
            send_desktop_notification(
                title="Personal AI News Intelligence",
                message=f"Laporan berita terbaru siap ({len(report_articles)} artikel teranalisis). Buka output/latest_report.html.",
            )
            return {
                "status": "SUCCESS",
                "run_id": run_id,
                "fetch_stats": fetch_stats,
                "newly_processed_count": len(newly_processed),
                "report_articles_count": len(report_articles),
                "dated_report_path": str(paths["dated_path"]),
                "latest_report_path": str(paths["latest_path"]),
                "gmail_digest": gmail_status,
                "ai_engine": self.ai_engine.active_engine_label,
            }

        except Exception as exc:
            logger.exception("Pipeline failed with error: %s", exc)
            self.db.log_run_finish(
                run_id=run_id,
                feeds_checked=0,
                articles_fetched=0,
                duplicates_skipped=0,
                articles_processed=0,
                ai_provider=self.ai_engine.active_engine_label,
                output_file="",
                status="ERROR",
                error_details=str(exc),
            )
            raise


def has_sent_today() -> bool:
    """Checks if today's Telegram news briefing has already been delivered."""
    from datetime import datetime
    from config.settings import BASE_DIR
    stamp_file = BASE_DIR / "data" / "last_telegram_sent_date.txt"
    if not stamp_file.exists():
        return False
    try:
        last_date = stamp_file.read_text(encoding="utf-8").strip()
        return last_date == datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return False


def start_scheduler_daemon(interval_hours: int = SCHEDULE_INTERVAL_HOURS) -> None:
    """
    Runs a resilient background daemon that guarantees the daily 09:00 WIB Telegram briefing is sent:
    - Fires right at 09:00 WIB if the laptop is on.
    - If the laptop was asleep/off at 09:00 WIB and turned on later in the day, immediately catches up
      and sends today's briefing as soon as internet connectivity is available.
    - Never sends duplicate automatic briefings on the same day.
    """
    import time
    from datetime import datetime

    workflow = NewsAggregationWorkflow()

    try:
        hour_str, min_str = DAILY_NOTIFICATION_TIME.split(":")
        daily_hour, daily_min = int(hour_str), int(min_str)
    except Exception:
        daily_hour, daily_min = 9, 0

    logger.info(
        "Resilient Background Daemon started. Target schedule: %02d:%02d WIB daily (with sleep/boot catch-up).",
        daily_hour,
        daily_min,
    )

    try:
        while True:
            now = datetime.now()
            is_past_target_time = (now.hour, now.minute) >= (daily_hour, daily_min)

            if is_past_target_time and not has_sent_today():
                logger.info(
                    "Triggering daily 09:00 WIB Telegram briefing for %s (current time %02d:%02d WIB)...",
                    now.strftime("%Y-%m-%d"),
                    now.hour,
                    now.minute,
                )
                try:
                    res = workflow.execute_pipeline(trigger_type="DAILY_0900_AUTO_DAEMON")
                    if res.get("gmail_digest", {}).get("sent"):
                        logger.info("Daily Telegram briefing for %s delivered successfully!", now.strftime("%Y-%m-%d"))
                    else:
                        logger.warning("Pipeline ran but Telegram not yet confirmed sent; will retry in 60s.")
                except Exception as exc:
                    logger.warning("Scheduled run encountered temporary error (%s); will retry in 60s.", exc)

            time.sleep(45)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Background scheduler daemon stopped cleanly.")

