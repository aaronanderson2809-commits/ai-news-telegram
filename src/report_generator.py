"""
HTML5 Editorial News Report Generator.
Builds a complete, responsive, standalone HTML report (Times New Roman, Light Mode,
Executive Summary, 7 Categories, Rich News Cards, Closing Insights, and Verified Sources Table)
that opens directly in any browser without requiring an external web server.
"""
import html
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from config.settings import CATEGORIES, OUTPUT_DIR, TEMPLATE_DIR
from src.models import ProcessedArticle, ExecutiveSummary

logger = logging.getLogger(__name__)


def _esc(text: Any) -> str:
    """Safely HTML-escapes any string."""
    return html.escape(str(text or ""), quote=True)


class ReportGenerator:
    """Generates standalone HTML5 intelligence reports from processed articles."""

    def __init__(self, output_dir: Path = OUTPUT_DIR, template_dir: Path = TEMPLATE_DIR):
        self.output_dir = Path(output_dir)
        self.template_dir = Path(template_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(
        self,
        articles: List[ProcessedArticle],
        exec_summary: ExecutiveSummary,
        db_stats: Dict[str, Any],
    ) -> Dict[str, Path]:
        """
        Renders the full HTML report and saves both a timestamped file
        and `latest_report.html` in the output directory.
        """
        now = datetime.now()
        report_date_iso = now.strftime("%Y-%m-%d")
        report_date_readable = now.strftime("%d %B %Y")
        generated_timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = now.strftime("%Y-%m-%d_%H%M%S")

        # Load CSS, JS, and HTML Template
        css_content = (self.template_dir / "styles.css").read_text(encoding="utf-8")
        js_content = (self.template_dir / "app.js").read_text(encoding="utf-8")
        template_html = (self.template_dir / "report_template.html").read_text(encoding="utf-8")

        # Group articles into the 7 required categories
        grouped: Dict[str, List[ProcessedArticle]] = {cat: [] for cat in CATEGORIES}
        for art in articles:
            target_cat = art.category if art.category in grouped else "Dunia"
            grouped[target_cat].append(art)

        # Sort articles inside each category by published_at descending
        for cat in grouped:
            grouped[cat].sort(key=lambda a: a.published_at, reverse=True)

        total_articles = len(articles)
        distinct_sources = len({a.source for a in articles})
        sent_pos = sum(1 for a in articles if a.sentiment == "Positif")
        sent_neu = sum(1 for a in articles if a.sentiment == "Netral")
        sent_neg = sum(1 for a in articles if a.sentiment == "Negatif")

        # 1. Build Category Nav Pills & Select Options & Dashboard Stat Cards
        nav_pills_html: List[str] = []
        select_options_html: List[str] = []
        stat_cards_html: List[str] = []

        # "Semua Kategori" card first in dashboard
        stat_cards_html.append(
            f"""
            <div class="stat-card active-stat" data-category="ALL">
                <div class="stat-card-label">Semua Kategori Berita</div>
                <div class="stat-card-value">
                    <span>{total_articles}</span>
                    <span class="stat-card-pct">100%</span>
                </div>
                <div class="stat-bar-track">
                    <div class="stat-bar-fill" style="width:100%;"></div>
                </div>
            </div>
            """
        )

        for cat in CATEGORIES:
            count = len(grouped[cat])
            pct = round((count / total_articles * 100), 1) if total_articles > 0 else 0.0
            cat_esc = _esc(cat)

            nav_pills_html.append(
                f'<button type="button" class="nav-pill" data-category="{cat_esc}">'
                f'{cat_esc} <span class="pill-count">{count}</span></button>'
            )
            select_options_html.append(
                f'<option value="{cat_esc}">{cat_esc} ({count})</option>'
            )
            stat_cards_html.append(
                f"""
                <div class="stat-card" data-category="{cat_esc}">
                    <div class="stat-card-label">{cat_esc}</div>
                    <div class="stat-card-value">
                        <span>{count}</span>
                        <span class="stat-card-pct">{pct}%</span>
                    </div>
                    <div class="stat-bar-track">
                        <div class="stat-bar-fill" style="width:{min(100, max(4, pct))}%;"></div>
                    </div>
                </div>
                """
            )

        # 2. Build Executive Summary Key Issues HTML
        key_issues_items: List[str] = []
        for idx, issue in enumerate(exec_summary.key_issues, start=1):
            t_str = _esc(issue.get("title", f"Isu Utama {idx}"))
            d_str = _esc(issue.get("description", ""))
            key_issues_items.append(
                f"""
                <li class="key-issue-item">
                    <div class="key-issue-title">{idx}. {t_str}</div>
                    <div class="key-issue-desc">{d_str}</div>
                </li>
                """
            )

        # 3. Build Category Sections & News Cards HTML
        category_sections_html: List[str] = []
        for cat in CATEGORIES:
            cat_articles = grouped[cat]
            cat_esc = _esc(cat)
            cards_html = [self._render_news_card(art) for art in cat_articles]

            section_block = f"""
            <section class="category-section" data-category-section="{cat_esc}">
                <div class="category-banner">
                    <h2 class="category-banner-title">{cat_esc}</h2>
                    <span class="category-banner-count">{len(cat_articles)} Berita Ditampilkan</span>
                </div>
                <div class="news-cards-grid">
                    {"".join(cards_html)}
                </div>
            </section>
            """
            category_sections_html.append(section_block)

        # 4. Build Closing Macro Trends HTML
        macro_trends_html = "\n".join(
            f"<li>{_esc(trend)}</li>" for trend in exec_summary.macro_trends
        )

        # 5. Build Sources Table Rows HTML
        sources_rows_html: List[str] = []
        for idx, art in enumerate(articles, start=1):
            sources_rows_html.append(
                f"""
                <tr>
                    <td>{idx}</td>
                    <td><strong>{_esc(art.source)}</strong><br><span style="font-size:0.78rem; color:var(--text-muted);">{_esc(art.feed_name)}</span></td>
                    <td><span class="category-tag">{_esc(art.category)}</span></td>
                    <td>{_esc(art.title)}</td>
                    <td>{_esc(art.published_at)}</td>
                    <td><span class="sentiment-badge sentiment-{_esc(art.sentiment)}">{_esc(art.sentiment)}</span></td>
                    <td><a href="{_esc(art.url)}" target="_blank" rel="noopener noreferrer">Buka Artikel ↗</a></td>
                </tr>
                """
            )

        # Replace placeholders in template
        replacements = {
            "{{INLINE_CSS}}": css_content,
            "{{INLINE_JS}}": js_content,
            "{{REPORT_DATE_ISO}}": report_date_iso,
            "{{REPORT_DATE_READABLE}}": report_date_readable,
            "{{GENERATED_TIMESTAMP}}": generated_timestamp,
            "{{AI_ENGINE_BADGE}}": _esc(exec_summary.generated_by),
            "{{TOTAL_ARTICLES}}": str(total_articles),
            "{{TOTAL_SOURCES}}": str(distinct_sources),
            "{{SENTIMENT_POS}}": str(sent_pos),
            "{{SENTIMENT_NEU}}": str(sent_neu),
            "{{SENTIMENT_NEG}}": str(sent_neg),
            "{{TOTAL_DB_ARTICLES}}": str(db_stats.get("total_stored", total_articles)),
            "{{CATEGORY_NAV_PILLS}}": "\n".join(nav_pills_html),
            "{{EXEC_OVERVIEW}}": _esc(exec_summary.overview),
            "{{EXEC_KEY_ISSUES_HTML}}": "\n".join(key_issues_items),
            "{{EXEC_GLOBAL_OUTLOOK}}": _esc(exec_summary.global_outlook),
            "{{DASHBOARD_STAT_CARDS_HTML}}": "\n".join(stat_cards_html),
            "{{CATEGORY_SELECT_OPTIONS}}": "\n".join(select_options_html),
            "{{NEWS_CATEGORIES_SECTIONS_HTML}}": "\n".join(category_sections_html),
            "{{CLOSING_INSIGHTS_TEXT}}": _esc(exec_summary.closing_insights),
            "{{MACRO_TRENDS_HTML}}": macro_trends_html,
            "{{SOURCES_TABLE_ROWS_HTML}}": "\n".join(sources_rows_html),
        }

        final_html = template_html
        for key, val in replacements.items():
            final_html = final_html.replace(key, val)

        dated_path = self.output_dir / f"news_report_{file_timestamp}.html"
        latest_path = self.output_dir / "latest_report.html"

        dated_path.write_text(final_html, encoding="utf-8")
        latest_path.write_text(final_html, encoding="utf-8")

        logger.info("Generated HTML reports: %s and %s", dated_path, latest_path)
        return {"dated_path": dated_path, "latest_path": latest_path}

    @staticmethod
    def _render_news_card(art: ProcessedArticle) -> str:
        """Renders an individual editorial news card with all required sections."""
        search_blob = " ".join(
            [
                art.title,
                art.headline_id,
                art.source,
                art.category,
                art.summary_id,
                art.core_issue,
                art.why_it_matters,
                art.ai_interpretation,
                " ".join(art.keywords),
            ]
        )

        facts_li = "".join(f"<li>{_esc(f)}</li>" for f in art.verified_facts)
        keywords_chips = "".join(
            f'<span class="keyword-chip" data-keyword="{_esc(kw)}" title="Klik untuk memfilter kata kunci ini">#{_esc(kw)}</span>'
            for kw in art.keywords
        )

        status_badge_color = "#065f46" if art.ai_status == "SUCCESS" else "#1b365d"

        return f"""
        <article class="news-card"
                 data-category="{_esc(art.category)}"
                 data-date="{_esc(art.published_date)}"
                 data-timestamp="{_esc(art.published_at)}"
                 data-sentiment="{_esc(art.sentiment)}"
                 data-sentiment-score="{art.sentiment_score}"
                 data-source="{_esc(art.source)}"
                 data-search="{_esc(search_blob)}">
            <div>
                <div class="card-top-meta">
                    <div>
                        <span class="source-badge">{_esc(art.source)}</span>
                        <span style="margin:0 6px; color:var(--border-medium);">|</span>
                        <span class="category-tag">{_esc(art.category)}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="pub-date">{_esc(art.published_at)}</span>
                        <span class="sentiment-badge sentiment-{_esc(art.sentiment)}" title="{_esc(art.sentiment_reason)}">
                            {_esc(art.sentiment)} ({art.sentiment_score:+.2f})
                        </span>
                    </div>
                </div>

                <h3 class="card-headline">
                    <a href="{_esc(art.url)}" target="_blank" rel="noopener noreferrer">
                        {_esc(art.headline_id)}
                    </a>
                </h3>

                <div class="card-summary">
                    <strong>Ringkasan Berita (ID):</strong> {_esc(art.summary_id)}
                </div>

                <div class="insights-box">
                    <div class="insights-box-title">Key Insights &amp; Pemisahan Fakta vs Analisis AI</div>
                    <div class="insight-row">
                        <strong>• Inti Permasalahan:</strong> {_esc(art.core_issue)}
                    </div>
                    <div class="insight-row">
                        <strong>• Mengapa Berita Ini Penting:</strong> {_esc(art.why_it_matters)}
                    </div>
                    <div class="insight-row">
                        <strong>• Fakta Terverifikasi Sumber ({_esc(art.source)}):</strong>
                        <ul class="facts-list">
                            {facts_li}
                        </ul>
                    </div>
                    <div class="ai-interpretation-box">
                        <strong>Analisis &amp; Interpretasi AI:</strong> {_esc(art.ai_interpretation)}
                        <div style="margin-top:4px; font-size:0.8rem; color:var(--text-muted);">
                            <em>Alasan Sentimen ({_esc(art.sentiment)}): {_esc(art.sentiment_reason)}</em>
                        </div>
                    </div>
                </div>

                <div style="margin-bottom:6px; font-size:0.84rem; font-weight:700; text-transform:uppercase; color:var(--brand-navy);">
                    Potential Impact (Potensi Dampak Sektoral)
                </div>
                <div class="impact-grid">
                    <div class="impact-cell">
                        <div class="impact-cell-title">Ekonomi &amp; Pasar</div>
                        <div>{_esc(art.potential_impact.economy)}</div>
                    </div>
                    <div class="impact-cell">
                        <div class="impact-cell-title">Teknologi &amp; Inovasi</div>
                        <div>{_esc(art.potential_impact.technology)}</div>
                    </div>
                    <div class="impact-cell">
                        <div class="impact-cell-title">Industri &amp; Rantai Pasok</div>
                        <div>{_esc(art.potential_impact.industry)}</div>
                    </div>
                    <div class="impact-cell">
                        <div class="impact-cell-title">Masyarakat &amp; Kebijakan</div>
                        <div>{_esc(art.potential_impact.society)}</div>
                    </div>
                </div>
            </div>

            <div class="card-footer">
                <div>
                    <div class="keywords-wrap">{keywords_chips}</div>
                    <div style="margin-top:6px; font-size:0.75rem; color:{status_badge_color};">
                        Status Pemrosesan: <strong>{_esc(art.ai_status)}</strong>
                    </div>
                </div>
                <a href="{_esc(art.url)}" target="_blank" rel="noopener noreferrer" class="btn-editorial">
                    Baca Artikel Asli ↗
                </a>
            </div>
        </article>
        """

