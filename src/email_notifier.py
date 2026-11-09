"""
Mobile Notification & Crucial News Digest Module (Telegram Bot & Optional Gmail).
Selects high-impact news across 5 structured intelligence sections:
1. Bisnis, Korporasi & Akuisisi (Konglomerat, M&A, Investasi Besar, Strategi, PHK Massal)
2. AI & Inovasi Teknologi (Peluncuran Model/Produk Baru, Industri Teknologi, Dampak Bisnis/Masyarakat)
3. Pasar Keuangan, Komoditas & Kripto (Saham, Obligasi, Komoditas, Valas, Kripto + Konteks Tanpa Saran Investasi)
4. Geopolitik & Kebijakan Global (Kebijakan Negara, Konflik, Diplomasi, Sanksi, Pemilu)
5. KHUSUS UNTUK GEOFISIKA & ENERGI BERSIH (Gempa Bumi, Gunung Api, Panas Bumi, Survei/Teknologi Geofisika, Geoneutrino, Energi Bersih)
"""
import html
import logging
import re
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import httpx

from config.settings import (
    ENABLE_TELEGRAM_NOTIFICATION,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    ENABLE_GMAIL_NOTIFICATION,
    GMAIL_SENDER,
    GMAIL_APP_PASSWORD,
    GMAIL_RECIPIENT,
    SMTP_HOST,
    SMTP_PORT,
    OUTPUT_DIR,
    BASE_DIR,
)
from src.models import ProcessedArticle, ExecutiveSummary

logger = logging.getLogger(__name__)

# --- Section Trigger Keywords ---

GEOPHYSICS_AND_CLEAN_ENERGY_TRIGGERS = [
    "earthquake", "gempa", "seismic", "seismik", "seismology", "volcano", "volcanic",
    "gunung api", "eruption", "magma", "caldera", "geothermal", "panas bumi",
    "geophysics", "geophysical", "geofisika", "geoneutrino", "neutrino", "subsurface",
    "tectonic", "tektonik", "tsunami", "usgs", "clean energy", "energi bersih",
    "renewable", "energi terbarukan", "green hydrogen", "hidrogen hijau", "nuclear fusion",
    "fusi nuklir", "solar", "wind farm", "wind power", "carbon capture", "grid"
]

CORPORATE_AND_BUSINESS_TRIGGERS = [
    "merger", "acquisition", "acquires", "acquired", "buyout", "takeover", "deal",
    "sells", "sold", "billion", "trillion", "valuation", "funding", "raises", "raised",
    "investment", "invests", "ipo", "conglomerate", "ceo", "executive", "founder",
    "layoff", "layoffs", "job cuts", "restructuring", "bankruptcy", "lawsuit",
    "antitrust", "strategy", "launch", "launches", "unveils", "partnership", "profit", "revenue"
]

AI_AND_TECH_TRIGGERS = [
    "artificial intelligence", "new ai", "ai model", "llm", "generative ai",
    "openai", "gemini", "deepmind", "anthropic", "claude", "gpt", "nvidia",
    "semiconductor", "chip", "data center", "robotics", "humanoid", "quantum",
    "cybersecurity", "cloud", "autonomous", "apple", "microsoft", "google", "meta", "deepseek"
]

MARKETS_AND_CRYPTO_TRIGGERS = [
    "stock", "stocks", "wall street", "s&p", "nasdaq", "dow", "shares", "equity",
    "bond", "bonds", "treasury", "yield", "yields", "commodity", "commodities",
    "gold", "oil", "crude", "brent", "wti", "copper", "nickel", "lithium",
    "currency", "dollar", "forex", "yen", "euro", "rupiah", "inflation",
    "interest rate", "central bank", "fed", "federal reserve", "gdp",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "etf", "stablecoin", "blockchain"
]

GEOPOLITICS_AND_POLICY_TRIGGERS = [
    "geopolitics", "geopolitical", "sanctions", "tariff", "tariffs", "trade war",
    "conflict", "war", "ceasefire", "military", "defense", "pentagon", "nato",
    "united nations", "summit", "treaty", "diplomacy", "bilateral", "election",
    "parliament", "congress", "white house", "kremlin", "beijing", "policy", "regulation"
]


def _translate_text_id(text: str) -> str:
    """Translates text into natural Bahasa Indonesia via Google GTX endpoint if still in English."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    try:
        resp = httpx.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "id", "dt": "t", "q": cleaned},
            timeout=6.0,
        )
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, list) and payload and isinstance(payload[0], list):
                translated = "".join(seg[0] for seg in payload[0] if seg and seg[0])
                if translated.strip():
                    return translated.strip()
    except Exception:
        pass
    return cleaned


def clean_and_polish_article_text(art: ProcessedArticle) -> Dict[str, str]:
    """
    Ensures every selected article has a clean, systematic, non-repetitive Bahasa Indonesia
    Headline, Summary (Inti Berita), and Context/Impact (Konteks & Dampak), removing any legacy
    template boilerplate like 'Berdasarkan laporan X pada Y, artikel berjudul Z...'.
    """
    raw_title = re.sub(r"(\s+-\s+[^-]+)+$", "", (art.title or "").strip()).strip()
    raw_desc = re.sub(r"(\s+-\s+[^-]+)+$", "", (art.raw_description or "").strip()).strip()
    if raw_desc.endswith("..."):
        raw_desc = raw_desc[:-3].strip()

    # 1. Clean & Translate Headline
    headline = (art.headline_id or raw_title).strip()
    headline = re.sub(r"(\s+-\s+[^-]+)+$", "", headline).strip()
    if headline.lower() == raw_title.lower() or " - " in headline:
        headline = _translate_text_id(raw_title)
        headline = re.sub(r"(\s+-\s+[^-]+)+$", "", headline).strip()

    # 2. Clean & Translate Summary (strip old repetitive boilerplate or Google News fallback strings)
    summary = (art.summary_id or "").strip()
    is_google_news_placeholder = (
        "Berita terbaru yang dilaporkan oleh " in raw_desc
        or "Berita terbaru yang dilaporkan oleh " in summary
    )
    if is_google_news_placeholder:
        summary = f"Laporan utama {art.source} menyoroti {headline[0].lower() + headline[1:] if len(headline) > 1 else headline}."
    elif "Berdasarkan laporan " in summary or "Inti kutipan laporan sumber menyebutkan:" in summary or not summary:
        if raw_desc and raw_desc.lower() != raw_title.lower():
            summary = _translate_text_id(raw_desc[:360])
        else:
            summary = f"Laporan utama {art.source} menyoroti {headline[0].lower() + headline[1:] if len(headline) > 1 else headline}."
    elif summary.lower() == raw_desc.lower():
        summary = _translate_text_id(summary[:360])

    if summary and not summary.endswith("."):
        summary += "."

    # Avoid exact duplication between headline and summary
    if summary.rstrip(".").strip().lower() == headline.rstrip(".").strip().lower():
        summary = f"Laporan {art.source} menyoroti perkembangan strategis terkait {headline[0].lower() + headline[1:] if len(headline) > 1 else headline}."

    # 3. Build concise, non-repetitive Context & Impact (1-2 crisp sentences, no repeated article title)
    combined_low = f"{raw_title} {raw_desc}".lower()
    if any(k in combined_low for k in GEOPHYSICS_AND_CLEAN_ENERGY_TRIGGERS[:18]):
        context_impact = (
            "Penting bagi pemantauan aktivitas seismik/vulkanik, pemetaan potensi bawah permukaan, "
            "serta akselerasi pengembangan energi panas bumi (geotermal) dan energi bersih."
        )
    elif any(k in combined_low for k in ("bitcoin", "crypto", "ethereum", "stock", "bond", "yield", "treasury", "currency", "fed", "inflation")):
        context_impact = (
            "Memberikan konteks faktual atas pergerakan likuiditas pasar keuangan, komoditas, dan aset kripto "
            "akibat sentimen makroekonomi global (informasi pasar faktual, bukan saran investasi)."
        )
    elif any(k in combined_low for k in ("merger", "acquisition", "buyout", "sells", "raises", "billion", "trillion", "valuation", "layoff", "ceo")):
        context_impact = (
            "Aksi korporasi dan pergeseran modal berskala besar ini berdampak langsung pada peta persaingan industri, "
            "valuasi bisnis, serta strategi operasional perusahaan global."
        )
    elif art.category == "AI & Technology" or any(k in combined_low for k in AI_AND_TECH_TRIGGERS):
        context_impact = (
            "Terobosan produk dan infrastruktur AI/teknologi ini mendorong efisiensi bisnis, transformasi industri, "
            "serta adopsi teknologi di tingkat korporasi maupun masyarakat."
        )
    elif art.category == "Geopolitics/politics" or any(k in combined_low for k in GEOPOLITICS_AND_POLICY_TRIGGERS):
        context_impact = (
            "Kebijakan strategis dan dinamika geopolitik antarnegara ini berpotensi memengaruhi stabilitas kawasan, "
            "rantai pasok perdagangan, serta sentimen pasar global."
        )
    else:
        why = (art.why_it_matters or "").strip()
        context_impact = why if why and "\"" not in why else (
            "Perkembangan strategis ini memiliki implikasi luas terhadap kebijakan industri, pelaku pasar, dan masyarakat."
        )

    return {
        "headline": headline,
        "summary": summary,
        "context_impact": context_impact,
        "sentiment": (
            "Waspada / Mitigasi"
            if any(w in combined_low for w in ("earthquake", "gempa", "volcano", "eruption", "gunung api"))
            else art.sentiment
        ),
    }


def _count_keyword_hits(text_lower: str, kw_list: List[str]) -> int:
    hits = 0
    for kw in kw_list:
        if len(kw) <= 4:
            if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                hits += 1
        elif kw in text_lower:
            hits += 1
    return hits


def organize_briefing_sections(
    articles: List[ProcessedArticle],
) -> List[Dict[str, Any]]:
    """
    Organizes articles systematically into the 5 high-impact sections requested by the user,
    with the dedicated 'KHUSUS UNTUK GEOFISIKA & ENERGI BERSIH' section placed at the very end.
    """
    used_urls = set()

    def pick_top(candidates: List[Tuple[float, ProcessedArticle]], limit: int) -> List[ProcessedArticle]:
        candidates.sort(key=lambda x: (x[0], x[1].published_at), reverse=True)
        picked: List[ProcessedArticle] = []
        for sc, art in candidates:
            if art.url not in used_urls and sc > 0:
                picked.append(art)
                used_urls.add(art.url)
                if len(picked) >= limit:
                    break
        return picked

    # First reserve Geophysics & Clean Energy items so the final dedicated section is always rich
    geophysics_candidates: List[Tuple[float, ProcessedArticle]] = []
    for art in articles:
        text_low = f"{art.title} {art.raw_description} {art.feed_name}".lower()
        geo_hits = _count_keyword_hits(text_low, GEOPHYSICS_AND_CLEAN_ENERGY_TRIGGERS)
        core_geo_hits = _count_keyword_hits(
            text_low,
            [
                "earthquake", "gempa", "seismic", "seismology", "volcano", "volcanic",
                "eruption", "geothermal", "panas bumi", "geophysics", "geophysical",
                "geoneutrino", "subsurface", "tectonic", "clean energy", "renewable",
                "hydrogen", "fusion", "solar", "wind",
            ],
        )
        if core_geo_hits > 0 or art.category == "Energy & Renewable Energy":
            score = core_geo_hits * 4.0 + geo_hits * 2.0 + (3.0 if art.category == "Energy & Renewable Energy" else 0.0)
            geophysics_candidates.append((score, art))

    geophysics_items = pick_top(geophysics_candidates, limit=3)

    # 1. Bisnis, Korporasi & Akuisisi
    corp_candidates: List[Tuple[float, ProcessedArticle]] = []
    for art in articles:
        if art.url in used_urls:
            continue
        text_low = f"{art.title} {art.raw_description}".lower()
        hits = _count_keyword_hits(text_low, CORPORATE_AND_BUSINESS_TRIGGERS)
        if hits > 0:
            score = hits * 3.5 + abs(art.sentiment_score) * 2.0
            corp_candidates.append((score, art))
    corp_items = pick_top(corp_candidates, limit=2)

    # 2. AI & Inovasi Teknologi
    ai_candidates: List[Tuple[float, ProcessedArticle]] = []
    for art in articles:
        if art.url in used_urls:
            continue
        text_low = f"{art.title} {art.raw_description}".lower()
        hits = _count_keyword_hits(text_low, AI_AND_TECH_TRIGGERS)
        if art.category == "AI & Technology" or hits > 0:
            score = hits * 3.0 + (4.0 if art.category == "AI & Technology" else 0.0) + abs(art.sentiment_score) * 2.0
            ai_candidates.append((score, art))
    ai_items = pick_top(ai_candidates, limit=2)

    # 3. Pasar Keuangan, Komoditas & Kripto
    market_candidates: List[Tuple[float, ProcessedArticle]] = []
    for art in articles:
        if art.url in used_urls:
            continue
        text_low = f"{art.title} {art.raw_description}".lower()
        hits = _count_keyword_hits(text_low, MARKETS_AND_CRYPTO_TRIGGERS)
        if art.category in ("Economy & Finance & markets", "Cryptocurrency", "Mining, Oil & Gas") or hits > 0:
            score = hits * 3.0 + (3.5 if art.category in ("Economy & Finance & markets", "Cryptocurrency") else 1.5)
            market_candidates.append((score, art))
    market_items = pick_top(market_candidates, limit=2)

    # 4. Geopolitik & Kebijakan Global
    geopol_candidates: List[Tuple[float, ProcessedArticle]] = []
    for art in articles:
        if art.url in used_urls:
            continue
        text_low = f"{art.title} {art.raw_description}".lower()
        hits = _count_keyword_hits(text_low, GEOPOLITICS_AND_POLICY_TRIGGERS)
        if art.category in ("Geopolitics/politics", "Dunia") or hits > 0:
            score = hits * 3.0 + (3.5 if art.category == "Geopolitics/politics" else 1.5)
            geopol_candidates.append((score, art))
    geopol_items = pick_top(geopol_candidates, limit=2)

    sections = [
        {
            "code": "I",
            "icon": "🏢",
            "title": "BISNIS, KORPORASI & INVESTASI BESAR",
            "subtitle": "Aktivitas Konglomerat • Merger & Akuisisi • Strategi & Aksi Korporasi",
            "items": corp_items,
        },
        {
            "code": "II",
            "icon": "🤖",
            "title": "AI & INOVASI TEKNOLOGI",
            "subtitle": "Peluncuran Model/Produk Baru • Semikonduktor • Dampak Bisnis & Masyarakat",
            "items": ai_items,
        },
        {
            "code": "III",
            "icon": "📈",
            "title": "PASAR KEUANGAN, KOMODITAS & KRIPTO",
            "subtitle": "Saham • Obligasi • Komoditas • Valas • Aset Kripto (Konteks Faktual, Bukan Saran Investasi)",
            "items": market_items,
        },
        {
            "code": "IV",
            "icon": "🌍",
            "title": "POLITIK & GEOPOLITIK GLOBAL",
            "subtitle": "Kebijakan Strategis • Konflik & Diplomasi • Sanksi Ekonomi • Pemilu",
            "items": geopol_items,
        },
        {
            "code": "V",
            "icon": "🌋",
            "title": "KHUSUS UNTUK GEOFISIKA & ENERGI BERSIH",
            "subtitle": "Gempa Bumi • Gunung Api • Panas Bumi (Geotermal) • Survei Geofisika • Geoneutrino • Energi Bersih",
            "items": geophysics_items,
        },
    ]
    return [sec for sec in sections if sec["items"]]


def select_crucial_articles(
    articles: List[ProcessedArticle], max_items: int = 11
) -> List[Tuple[ProcessedArticle, str]]:
    """ Compatibility helper returning flattened (article, section_title) tuples. """
    sections = organize_briefing_sections(articles)
    flat: List[Tuple[ProcessedArticle, str]] = []
    for sec in sections:
        for art in sec["items"]:
            flat.append((art, f"{sec['icon']} {sec['title']}"))
    return flat[:max_items]


def build_telegram_messages(
    articles: List[ProcessedArticle],
    exec_summary: ExecutiveSummary,
    total_collected: int,
) -> List[str]:
    """
    Builds systematic, clean, and visually neat Telegram HTML messages grouped into 5 strategic sections,
    ending with the dedicated 'KHUSUS UNTUK GEOFISIKA & ENERGI BERSIH' section.
    """
    now_str = datetime.now().strftime("%d %B %Y • %H:%M WIB")
    sections = organize_briefing_sections(articles)
    total_selected = sum(len(s["items"]) for s in sections)

    header = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>BRIEFING INTELIJEN BERITA UTAMA</b>\n"
        f"📅 {html.escape(now_str)}\n"
        f"📊 <i>{total_selected} Berita Berdampak Tinggi dari {total_collected} Artikel Global</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧭 <b>GAMBARAN EKSEKUTIF</b>\n"
        f"{html.escape(exec_summary.overview)}"
    )

    chunks: List[str] = []
    current_msg = header
    global_idx = 1

    for sec in sections:
        sec_header = (
            f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sec['icon']} <b>{sec['code']}. {html.escape(sec['title'])}</b>\n"
            f"<i>{html.escape(sec['subtitle'])}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        if len(current_msg) + len(sec_header) > 3500:
            chunks.append(current_msg)
            current_msg = sec_header.lstrip("\n")
        else:
            current_msg += sec_header

        for art in sec["items"]:
            polished = clean_and_polish_article_text(art)
            disp_sent = polished["sentiment"]
            sent_emoji = (
                "🟠" if "Waspada" in disp_sent
                else ("🟢" if disp_sent == "Positif" else ("🔴" if disp_sent == "Negatif" else "⚪"))
            )

            item_block = (
                f"\n\n<b>{global_idx}. {html.escape(polished['headline'])}</b>\n"
                f"├ 📰 <b>Sumber:</b> {html.escape(art.source)}  •  {sent_emoji} {html.escape(disp_sent)}\n"
                f"├ 📌 <b>Inti Berita:</b> {html.escape(polished['summary'])}\n"
                f"├ 💡 <b>Konteks &amp; Dampak:</b> {html.escape(polished['context_impact'])}\n"
                f"└ 🔗 <a href=\"{html.escape(art.url)}\">Baca Artikel Asli di {html.escape(art.source)} ↗</a>"
            )
            global_idx += 1

            if len(current_msg) + len(item_block) > 3800:
                chunks.append(current_msg)
                current_msg = (
                    f"{sec['icon']} <b>{sec['code']}. {html.escape(sec['title'])} (Lanjutan)</b>"
                    + item_block
                )
            else:
                current_msg += item_block

    footer = (
        "\n\n──────────────────────\n"
        "ℹ️ <i>Catatan: Analisis pasar &amp; kripto disajikan murni sebagai konteks berita faktual, bukan saran investasi.</i>"
    )
    if len(current_msg) + len(footer) <= 4050:
        current_msg += footer
    else:
        chunks.append(current_msg)
        current_msg = footer.lstrip("\n")

    chunks.append(current_msg)
    return chunks


def build_gmail_mobile_html(
    articles: List[ProcessedArticle],
    exec_summary: ExecutiveSummary,
    total_collected: int,
) -> Tuple[str, str]:
    """
    Builds a responsive, systematic HTML preview (`output/latest_email_digest.html`) and plain-text fallback
    matching the 5 strategic sections including 'KHUSUS UNTUK GEOFISIKA & ENERGI BERSIH'.
    """
    now_str = datetime.now().strftime("%d %B %Y • %H:%M WIB")
    sections = organize_briefing_sections(articles)
    total_selected = sum(len(s["items"]) for s in sections)

    sections_html: List[str] = []
    plain_lines: List[str] = [
        f"PERSONAL AI NEWS INTELLIGENCE — BRIEFING BERITA BERDAMPAK TINGGI ({now_str})",
        "=" * 72,
        f"Gambaran Eksekutif: {exec_summary.overview}",
        "",
    ]

    global_idx = 1
    for sec in sections:
        is_geophysics = sec["code"] == "V"
        banner_bg = "#0f3d3e" if is_geophysics else "#1b365d"
        border_accent = "#0d9488" if is_geophysics else "#8b1e24"

        cards_html: List[str] = []
        plain_lines.append(f"[{sec['code']}. {sec['title']}]")
        plain_lines.append("-" * 72)

        for art in sec["items"]:
            polished = clean_and_polish_article_text(art)
            sent_color = (
                "#065f46" if art.sentiment == "Positif"
                else ("#991b1b" if art.sentiment == "Negatif" else "#374151")
            )
            sent_bg = (
                "#ecfdf5" if art.sentiment == "Positif"
                else ("#fef2f2" if art.sentiment == "Negatif" else "#f3f4f6")
            )

            cards_html.append(
                f"""
                <div style="background:#ffffff; border:1px solid #d1cec5; border-left:4px solid {border_accent}; border-radius:6px; padding:16px; margin-bottom:14px;">
                    <div style="font-size:11px; color:#5b6472; margin-bottom:6px; display:flex; justify-content:space-between; flex-wrap:wrap;">
                        <span><strong>#{global_idx}</strong> • 📰 <strong>{html.escape(art.source)}</strong> ({html.escape(art.published_date)})</span>
                        <span style="background:{sent_bg}; color:{sent_color}; padding:2px 7px; border-radius:3px; font-weight:bold;">
                            {html.escape(art.sentiment)}
                        </span>
                    </div>
                    <h3 style="font-family:'Times New Roman', Georgia, serif; font-size:18px; line-height:1.35; color:#111827; margin:0 0 10px 0;">
                        <a href="{html.escape(art.url)}" target="_blank" style="color:#1b365d; text-decoration:none;">
                            {html.escape(polished['headline'])}
                        </a>
                    </h3>
                    <div style="font-family:'Times New Roman', Georgia, serif; font-size:15px; line-height:1.55; color:#1f2937; background:#faf9f6; padding:10px 12px; border-radius:4px; margin-bottom:8px;">
                        <strong>📌 Inti Berita:</strong><br>
                        {html.escape(polished['summary'])}
                    </div>
                    <div style="font-family:'Times New Roman', Georgia, serif; font-size:14px; line-height:1.5; color:#374151; margin-bottom:10px;">
                        <strong>💡 Konteks &amp; Dampak:</strong><br>
                        {html.escape(polished['context_impact'])}
                    </div>
                    <div>
                        <a href="{html.escape(art.url)}" target="_blank" style="display:inline-block; background:{banner_bg}; color:#ffffff; text-decoration:none; font-family:'Times New Roman', Georgia, serif; font-size:13px; font-weight:bold; padding:6px 12px; border-radius:4px;">
                            Baca Artikel Asli di {html.escape(art.source)} ↗
                        </a>
                    </div>
                </div>
                """
            )
            plain_lines.extend(
                [
                    f"{global_idx}. {polished['headline']} ({art.source})",
                    f"   Inti Berita     : {polished['summary']}",
                    f"   Konteks & Dampak: {polished['context_impact']}",
                    f"   Link Asli       : {art.url}",
                    "",
                ]
            )
            global_idx += 1

        sections_html.append(
            f"""
            <div style="margin-top:22px; margin-bottom:16px;">
                <div style="background:{banner_bg}; color:#ffffff; padding:10px 14px; border-radius:5px; margin-bottom:12px;">
                    <div style="font-size:15px; font-weight:bold; letter-spacing:0.5px;">
                        {sec['icon']} {sec['code']}. {html.escape(sec['title'])}
                    </div>
                    <div style="font-size:12px; color:#e2e8f0; margin-top:2px;">
                        {html.escape(sec['subtitle'])}
                    </div>
                </div>
                {"".join(cards_html)}
            </div>
            """
        )

    html_body = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Briefing Berita Krusial Harian</title>
</head>
<body style="margin:0; padding:12px; background-color:#f3f1ec; font-family:'Times New Roman', Georgia, serif; color:#111827;">
    <div style="max-width:680px; margin:0 auto; background:#ffffff; border:1px solid #d1cec5; border-top:5px solid #1b365d; border-radius:6px; overflow:hidden;">
        <div style="padding:20px 18px; text-align:center; border-bottom:3px double #1f2937; background:#faf9f6;">
            <div style="display:inline-flex; align-items:center; gap:8px; background:#ecfdf5; border:1px solid #10b981; color:#065f46; padding:5px 12px; border-radius:999px; font-size:12px; font-weight:bold; margin-bottom:10px;">
                <span style="display:inline-block; width:10px; height:10px; background:#10b981; border-radius:50%;"></span>
                JADWAL OTOMATIS TELEGRAM (09:00 WIB): ON / AKTIF
            </div>
            <div style="font-size:11px; font-weight:bold; color:#8b1e24; letter-spacing:1px; text-transform:uppercase; margin-bottom:4px;">
                PERSONAL AI NEWS INTELLIGENCE • EXECUTIVE MOBILE BRIEFING
            </div>
            <h1 style="font-size:22px; margin:0 0 6px 0; color:#111827; letter-spacing:0.5px;">
                SOROTAN BERITA STRATEGIS &amp; GEOFISIKA HARI INI
            </h1>
            <div style="font-size:13px; color:#5b6472;">
                {html.escape(now_str)} • {total_selected} Berita Terpilih dari {total_collected} Artikel Global
            </div>
        </div>

        <div style="padding:16px 18px;">
            <div style="background:#f8f5f0; border-left:4px solid #1b365d; padding:12px 14px; margin-bottom:18px; font-size:14px; line-height:1.55; color:#374151;">
                <strong style="color:#1b365d; text-transform:uppercase;">🧭 Gambaran Eksekutif Singkat:</strong><br>
                {html.escape(exec_summary.overview)}
            </div>

            {"".join(sections_html)}

            <div style="background:#faf9f6; border:1px solid #e6e4dd; padding:12px 14px; font-size:12px; color:#5b6472; text-align:center; border-radius:4px;">
                <em>Catatan: Konteks pergerakan saham, obligasi, komoditas, valas, dan kripto disajikan murni sebagai informasi faktual berita, bukan saran investasi.</em><br>
                Laporan interaktif lengkap ({total_collected} berita) tersimpan di <code>output/latest_report.html</code>.
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html_body, "\n".join(plain_lines)


def resolve_telegram_chat_id(bot_token: str, configured_chat_id: str) -> Optional[str]:
    """
    Returns a valid Telegram chat_id. If TELEGRAM_CHAT_ID is not yet set in .env,
    automatically queries Telegram's `getUpdates` API to discover the chat_id from the
    user's latest `/start` message to the bot.
    """
    clean_id = configured_chat_id.strip()
    placeholders = {
        "",
        "isi_chat_id_telegram_anda",
        "otomatis_terdeteksi_atau_isi_chat_id_anda",
        "your_telegram_chat_id",
    }
    if clean_id and clean_id.lower() not in placeholders:
        return clean_id

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = httpx.get(url, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("result", [])
            for update in reversed(results):
                msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member")
                if msg and "chat" in msg and "id" in msg["chat"]:
                    detected_id = str(msg["chat"]["id"])
                    logger.info("Auto-detected Telegram chat_id=%s from bot /start message.", detected_id)
                    try:
                        env_file = BASE_DIR / ".env"
                        if env_file.exists():
                            env_text = env_file.read_text(encoding="utf-8")
                            if "TELEGRAM_CHAT_ID=" in env_text:
                                updated_env = re.sub(
                                    r"^TELEGRAM_CHAT_ID=.*$",
                                    f"TELEGRAM_CHAT_ID={detected_id}",
                                    env_text,
                                    flags=re.MULTILINE,
                                )
                                env_file.write_text(updated_env, encoding="utf-8")
                    except Exception:
                        pass
                    return detected_id
    except Exception as exc:
        logger.debug("Could not auto-detect Telegram chat_id via getUpdates: %s", exc)

    return None


def send_telegram_crucial_digest(
    articles: List[ProcessedArticle],
    exec_summary: ExecutiveSummary,
    total_collected: int,
) -> Dict[str, Any]:
    """
    Sends the systematic 5-section Crucial News Briefing directly to the user's Telegram app.
    """
    token = TELEGRAM_BOT_TOKEN.strip()
    token_placeholders = {
        "",
        "masukkan_token_bot_telegram_dari_botfather",
        "your_telegram_bot_token",
    }
    if not ENABLE_TELEGRAM_NOTIFICATION or token.lower() in token_placeholders or ":" not in token:
        return {
            "sent": False,
            "channel": "telegram",
            "reason": "TELEGRAM_BOT_TOKEN_NOT_SET",
        }

    chat_id = resolve_telegram_chat_id(token, TELEGRAM_CHAT_ID)
    if not chat_id:
        logger.warning(
            "Telegram Bot Token is set, but chat_id could not be detected yet. "
            "Open your bot in Telegram and tap 'Start' (or send '/start'), or fill TELEGRAM_CHAT_ID in .env."
        )
        return {
            "sent": False,
            "channel": "telegram",
            "reason": "TELEGRAM_CHAT_ID_NOT_FOUND_SEND_START_TO_BOT",
        }

    sections = organize_briefing_sections(articles)
    total_selected = sum(len(s["items"]) for s in sections)
    messages = build_telegram_messages(articles, exec_summary, total_collected)
    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent_chunks = 0

    try:
        with httpx.Client(timeout=20.0) as client:
            for msg_text in messages:
                payload = {
                    "chat_id": chat_id,
                    "text": msg_text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                for attempt in range(3):
                    try:
                        resp = client.post(send_url, json=payload)
                        resp.raise_for_status()
                        sent_chunks += 1
                        time.sleep(0.5)
                        break
                    except Exception as retry_exc:
                        if attempt == 2:
                            raise retry_exc
                        time.sleep(1.2)

        logger.info(
            "Successfully sent systematic news briefing (%d items, %d messages) to Telegram chat_id=%s",
            total_selected,
            sent_chunks,
            chat_id,
        )
        try:
            stamp_file = BASE_DIR / "data" / "last_telegram_sent_date.txt"
            stamp_file.parent.mkdir(parents=True, exist_ok=True)
            stamp_file.write_text(datetime.now().strftime("%Y-%m-%d"), encoding="utf-8")
        except Exception:
            pass
        return {
            "sent": True,
            "channel": "telegram",
            "recipient": f"Telegram (chat_id: {chat_id})",
            "chat_id": chat_id,
            "crucial_count": total_selected,
        }
    except Exception as exc:
        if sent_chunks > 0:
            try:
                stamp_file = BASE_DIR / "data" / "last_telegram_sent_date.txt"
                stamp_file.parent.mkdir(parents=True, exist_ok=True)
                stamp_file.write_text(datetime.now().strftime("%Y-%m-%d"), encoding="utf-8")
            except Exception:
                pass
            return {
                "sent": True,
                "channel": "telegram",
                "recipient": f"Telegram (chat_id: {chat_id})",
                "chat_id": chat_id,
                "crucial_count": total_selected,
            }
        logger.error("Failed to send Telegram notification to chat_id=%s: %s", chat_id, exc)
        return {
            "sent": False,
            "channel": "telegram",
            "reason": str(exc),
        }


def send_crucial_gmail_digest(
    articles: List[ProcessedArticle],
    exec_summary: ExecutiveSummary,
) -> Dict[str, Any]:
    """
    Organizes the 5-section strategic briefing (including KHUSUS UNTUK GEOFISIKA),
    saves the preview to `output/latest_email_digest.html`, and sends to Telegram.
    """
    sections = organize_briefing_sections(articles)
    total_selected = sum(len(s["items"]) for s in sections)
    html_body, plain_body = build_gmail_mobile_html(
        articles=articles,
        exec_summary=exec_summary,
        total_collected=len(articles),
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    digest_preview_path: Path = OUTPUT_DIR / "latest_email_digest.html"
    digest_preview_path.write_text(html_body, encoding="utf-8")

    telegram_result = send_telegram_crucial_digest(
        articles=articles,
        exec_summary=exec_summary,
        total_collected=len(articles),
    )
    if telegram_result.get("sent"):
        return {
            "sent": True,
            "channel": "telegram",
            "recipient": telegram_result.get("recipient"),
            "preview_path": str(digest_preview_path),
            "crucial_count": total_selected,
        }

    sender = GMAIL_SENDER.strip()
    app_password = GMAIL_APP_PASSWORD.strip().replace(" ", "")
    recipient = (GMAIL_RECIPIENT.strip() or sender)

    has_valid_creds = bool(
        sender
        and "@" in sender
        and sender != "alamat_email_anda@gmail.com"
        and app_password
        and app_password != "16_digit_app_password_google"
        and len(app_password) >= 8
    )

    if not ENABLE_GMAIL_NOTIFICATION or not has_valid_creds:
        logger.info(
            "Mobile digest preview saved to %s. (Telegram status: %s)",
            digest_preview_path,
            telegram_result.get("reason", "NOT_CONFIGURED"),
        )
        return {
            "sent": False,
            "channel": "telegram",
            "reason": telegram_result.get("reason", "TELEGRAM_BOT_TOKEN_NOT_SET"),
            "preview_path": str(digest_preview_path),
            "crucial_count": total_selected,
        }

    subject_date = datetime.now().strftime("%d %b %Y")
    subject = f"🔥 [Briefing Intelijen & Geofisika {subject_date}] {total_selected} Berita Strategis Hari Ini"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Personal AI News Intelligence <{sender}>"
    msg["To"] = recipient

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender, app_password)
            server.sendmail(sender, [recipient], msg.as_string())

        return {
            "sent": True,
            "recipient": recipient,
            "preview_path": str(digest_preview_path),
            "crucial_count": total_selected,
        }
    except Exception as exc:
        logger.error("Failed to send Gmail notification to %s: %s", recipient, exc)
        return {
            "sent": False,
            "reason": str(exc),
            "preview_path": str(digest_preview_path),
            "crucial_count": total_selected,
        }
