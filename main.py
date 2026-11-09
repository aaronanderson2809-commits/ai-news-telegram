"""
Main Entry Point for Personal AI News Aggregator.
Supports:
- One-shot execution: `python main.py --run-once`
- Scheduled daemon execution via APScheduler: `python main.py --schedule`
- Regenerating HTML from existing SQLite database: `python main.py --report-only`
- Optional lightweight local API server for one-click HTML regeneration: `python main.py --serve`
"""
import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler

from config.settings import LOG_DIR, LOG_LEVEL, SCHEDULE_INTERVAL_HOURS
from src.scheduler import NewsAggregationWorkflow, start_scheduler_daemon


def setup_logging() -> None:
    """Configures both console and rotating file logging."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "aggregator.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Clear existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


class LocalRegenerateHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP handler allowing the standalone HTML report to trigger a refresh."""

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:
        if self.path == "/api/regenerate":
            workflow = NewsAggregationWorkflow()
            result = workflow.execute_pipeline(trigger_type="UI_BUTTON_TRIGGER")
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Personal AI News Intelligence Aggregator & Automated HTML Report Generator"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Execute the full news collection, AI analysis, and HTML report generation once and exit.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start APScheduler daemon to run the news aggregation workflow periodically.",
    )
    parser.add_argument(
        "--interval-hours",
        type=int,
        default=SCHEDULE_INTERVAL_HOURS,
        help=f"Interval in hours for scheduled runs (default: {SCHEDULE_INTERVAL_HOURS}).",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-fetch and process articles even if their URLs already exist in SQLite.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate a fresh HTML report directly from existing SQLite records without fetching RSS.",
    )
    parser.add_argument(
        "--reanalyze-db",
        action="store_true",
        help="Re-analyze existing articles in SQLite using the currently configured AI Engine and regenerate HTML.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local trigger API on http://127.0.0.1:8765 for the HTML Regenerate button.",
    )

    args = parser.parse_args()
    workflow = NewsAggregationWorkflow()

    if args.reanalyze_db:
        from config.settings import TRUSTED_FEEDS
        from src.models import RawArticle
        feed_map = {f["name"]: f["default_category"] for f in TRUSTED_FEEDS}
        existing = workflow.db.get_recent_articles(limit=50)
        raw_list = [
            RawArticle(
                title=a.title,
                source=a.source,
                feed_name=a.feed_name,
                url=a.url,
                published_at=a.published_at,
                published_date=a.published_date,
                description=a.raw_description,
                default_category=feed_map.get(a.feed_name, a.category),
                url_hash=a.url_hash,
                title_hash=a.title_hash,
            )
            for a in reversed(existing)
        ]
        reanalyzed = workflow.ai_engine.analyze_articles_batch(raw_list, batch_size=7)
        for art in reanalyzed:
            workflow.db.save_article(art)
        updated_articles = workflow.db.get_recent_articles(limit=50)
        exec_summary = workflow.ai_engine.generate_executive_summary(updated_articles)
        stats = workflow.db.get_stats()
        paths = workflow.report_gen.generate_html_report(updated_articles, exec_summary, stats)
        print(f"\n[OK] Re-analyzed {len(reanalyzed)} articles via {workflow.ai_engine.active_engine_label}")
        print(f"[OK] Updated HTML Report: {paths['latest_path']}")
        return

    if args.report_only:
        from src.email_notifier import send_crucial_gmail_digest
        articles = workflow.db.get_recent_articles(limit=50)
        exec_summary = workflow.ai_engine.generate_executive_summary(articles)
        stats = workflow.db.get_stats()
        paths = workflow.report_gen.generate_html_report(articles, exec_summary, stats)
        gmail_info = send_crucial_gmail_digest(articles, exec_summary)
        print(f"\n[OK] Generated HTML Report from SQLite: {paths['latest_path']}")
        print(f"[OK] Generated Mobile Digest Preview ({gmail_info['crucial_count']} crucial items): {gmail_info['preview_path']}")
        if gmail_info.get("sent"):
            print(f"[OK] Sent Crucial News Briefing to {gmail_info.get('recipient')}")
        return

    if args.schedule:
        start_scheduler_daemon(interval_hours=args.interval_hours)
        return

    if args.serve:
        server = HTTPServer(("127.0.0.1", 8765), LocalRegenerateHandler)
        logging.getLogger(__name__).info("Listening for regenerate triggers on http://127.0.0.1:8765 ...")
        server.serve_forever()
        return

    # Default action (--run-once or no flags): execute pipeline once
    result = workflow.execute_pipeline(
        trigger_type="CLI_MANUAL",
        force_refresh=args.force_refresh,
    )
    print("\n" + "=" * 78)
    print("PERSONAL AI NEWS INTELLIGENCE - EXECUTION SUMMARY")
    print("=" * 78)
    print(f"Status                 : {result['status']}")
    print(f"AI Engine Active       : {result['ai_engine']}")
    print(f"Feeds Checked          : {result['fetch_stats']['feeds_checked']} ({result['fetch_stats']['feeds_succeeded']} succeeded)")
    print(f"Raw Articles Fetched   : {result['fetch_stats']['raw_fetched']}")
    print(f"Duplicates Skipped     : {result['fetch_stats']['duplicates_skipped']}")
    print(f"New Articles Processed : {result['newly_processed_count']}")
    print(f"Total Articles in HTML : {result['report_articles_count']}")
    print(f"Dated HTML Report      : {result['dated_report_path']}")
    print(f"Latest HTML Report     : {result['latest_report_path']}")
    digest_status = result.get("gmail_digest", {})
    if digest_status.get("sent"):
        print(f"Telegram Notification  : SENT -> {digest_status.get('recipient')}")
    else:
        print(f"Telegram Notification  : PENDING ({digest_status.get('reason', 'NOT_SET')})")
    print("=" * 78)


if __name__ == "__main__":
    main()

