"""
Data models and schemas for Personal AI News Aggregator.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class RawArticle:
    """Represents a raw news item fetched from an RSS feed or public API."""
    title: str
    source: str
    feed_name: str
    url: str
    published_at: str          # ISO 8601 date string YYYY-MM-DD HH:MM:SS
    published_date: str        # YYYY-MM-DD for filtering
    description: str
    default_category: str
    url_hash: str
    title_hash: str
    url_verified: bool = True


@dataclass
class PotentialImpact:
    """Structured potential impact across Economy, Technology, Industry, and Society."""
    economy: str
    technology: str
    industry: str
    society: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ProcessedArticle:
    """Represents an AI-analyzed and categorized news article."""
    id: Optional[int]
    title: str
    headline_id: str           # Indonesian editorial headline / translation
    source: str
    feed_name: str
    url: str
    published_at: str
    published_date: str
    category: str
    raw_description: str
    # AI Analysis Fields
    summary_id: str            # Ringkasan berita dalam Bahasa Indonesia
    core_issue: str            # Inti permasalahan
    why_it_matters: str        # Mengapa berita tersebut penting
    verified_facts: List[str]  # Fakta dari sumber asli (dipisahkan dari interpretasi)
    ai_interpretation: str     # Analisis singkat AI (interpretasi terpisah dari fakta)
    potential_impact: PotentialImpact
    sentiment: str             # Positif | Negatif | Netral
    sentiment_score: float     # -1.0 to +1.0
    sentiment_reason: str      # Penjelasan singkat sentimen
    keywords: List[str]
    ai_provider_used: str      # e.g., "Gemini API (gemini-2.5-flash)" or "Analytical Engine"
    ai_status: str             # "SUCCESS" | "FALLBACK_ANALYTICAL" | "ERROR"
    url_hash: str
    title_hash: str
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["potential_impact"] = self.potential_impact.to_dict()
        return data


@dataclass
class ExecutiveSummary:
    """Executive Summary and Closing Insights for the entire intelligence report."""
    overview: str
    key_issues: List[Dict[str, str]]  # 3-5 main issues with title & description
    global_outlook: str
    closing_insights: str
    macro_trends: List[str]
    generated_by: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

