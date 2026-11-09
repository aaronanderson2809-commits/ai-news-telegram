"""
News Categorizer & Relevance Filter.
Assigns each article to one of the 7 required report categories based on multi-signal keyword scoring
and source context, while filtering out irrelevant entertainment/sports/gossip items.
"""
import re
from typing import Tuple, List
from config.settings import CATEGORIES, CATEGORY_KEYWORDS
from src.models import RawArticle

# Irrelevant / fluff / lifestyle topics to exclude
IRRELEVANT_PATTERNS = [
    r"\bceleb(rity|rities)?\b",
    r"\bgossip\b",
    r"\bhoroscope\b",
    r"\bfashion week\b",
    r"\bred carpet\b",
    r"\bpremier league\b",
    r"\bchampions league\b",
    r"\bnba\b",
    r"\bnfl\b",
    r"\blove island\b",
    r"\bkardashian\b",
    r"\bgift guide\b",
    r"\bbest deals\b",
    r"\bpromo code\b",
    r"\bwordle\b",
    r"\bcrossword\b",
    r"\brecipe\b",
]


def is_relevant_article(article: RawArticle) -> bool:
    """Checks that the article has valid content and is not pure entertainment/sports fluff."""
    if not article.title or len(article.title.strip()) < 12:
        return False
    if not article.url or not article.url.startswith(("http://", "https://")):
        return False

    combined = f"{article.title} {article.description}".lower()

    # Check if it matches any intelligence keyword first
    has_domain_keyword = any(
        kw.lower() in combined
        for kw_list in CATEGORY_KEYWORDS.values()
        for kw in kw_list
    )
    if has_domain_keyword:
        return True

    # Reject obvious entertainment/sports fluff
    for pattern in IRRELEVANT_PATTERNS:
        if re.search(pattern, combined):
            return False

    return True


def categorize_article(article: RawArticle) -> Tuple[str, List[str]]:
    """
    Classifies a RawArticle into one of the 7 target categories:
    1. AI & Technology
    2. Economy & Finance & markets
    3. Geopolitics/politics
    4. Energy & Renewable Energy
    5. Mining, Oil & Gas
    6. Dunia
    7. Cryptocurrency

    Returns (assigned_category, matched_keywords).
    """
    title_lower = article.title.lower()
    desc_lower = (article.description or "").lower()
    combined = f"{title_lower} {desc_lower}"

    scores = {cat: 0.0 for cat in CATEGORIES}
    matched_keywords: List[str] = []

    # Give a strong baseline preference to specialized domain feeds
    if article.default_category in scores:
        if article.default_category in ("Mining, Oil & Gas", "Energy & Renewable Energy", "Cryptocurrency"):
            scores[article.default_category] += 4.0
        else:
            scores[article.default_category] += 2.0

    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            kw_low = kw.lower()
            # Use word boundary matching for short acronyms (<=4 chars)
            if len(kw_low) <= 4:
                pattern = rf"\b{re.escape(kw_low)}\b"
                in_title = bool(re.search(pattern, title_lower))
                in_desc = bool(re.search(pattern, desc_lower))
            else:
                in_title = kw_low in title_lower
                in_desc = kw_low in desc_lower

            if in_title:
                scores[category] += 3.5
                if kw not in matched_keywords:
                    matched_keywords.append(kw)
            elif in_desc:
                scores[category] += 1.5
                if kw not in matched_keywords:
                    matched_keywords.append(kw)

    # Pick the category with the highest score
    best_cat = max(scores.items(), key=lambda item: item[1])[0]
    if scores[best_cat] <= 0:
        best_cat = article.default_category if article.default_category in CATEGORIES else "Dunia"

    # Ensure we always return at least 3 meaningful keywords
    if len(matched_keywords) < 3:
        fallback_tags = {
            "AI & Technology": ["Artificial Intelligence", "Teknologi Digital", "Inovasi"],
            "Economy & Finance & markets": ["Ekonomi Global", "Pasar Keuangan", "Makroekonomi"],
            "Geopolitics/politics": ["Geopolitik", "Hubungan Internasional", "Kebijakan Global"],
            "Energy & Renewable Energy": ["Transisi Energi", "Energi Terbarukan", "Kelistrikan"],
            "Mining, Oil & Gas": ["Komoditas Energi", "Minyak & Gas", "Pertambangan"],
            "Dunia": ["Perkembangan Global", "Internasional", "Berita Dunia"],
            "Cryptocurrency": ["Aset Digital", "Cryptocurrency", "Blockchain"],
        }
        for tag in fallback_tags.get(best_cat, ["Global Intelligence"]):
            if tag not in matched_keywords:
                matched_keywords.append(tag)
            if len(matched_keywords) >= 4:
                break

    return best_cat, matched_keywords[:6]
