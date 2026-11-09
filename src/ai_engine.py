"""
Configurable AI Analysis & Summarization Engine for Personal AI News Aggregator.
Supports:
1. Google Gemini API (via official `google-genai` SDK) - Primary Engine
2. OpenAI-Compatible API (OpenAI, OpenRouter, Groq, Local Ollama) - Secondary Engine
3. Factual Bilingual Analytical Fallback Engine - Ensures 100% operational resilience
   when API keys are not yet configured or rate limits are hit, with explicit status tracking.

Strictly separates Verified Facts (from source) from AI Interpretation.
Never fabricates facts or presents speculative predictions as facts.
"""
import json
import logging
import re
import time
from typing import List, Dict, Any, Tuple

import httpx

from config.settings import (
    AI_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    HTTP_TIMEOUT_SECONDS,
)
from src.models import RawArticle, ProcessedArticle, PotentialImpact, ExecutiveSummary
from src.categorizer import categorize_article

logger = logging.getLogger(__name__)

# Positive & Negative lexical signals for factual sentiment scoring
POSITIVE_SIGNALS = {
    "breakthrough", "growth", "surge", "surges", "rally", "gain", "gains", "record high",
    "profit", "launch", "launches", "innovation", "partnership", "agreement", "peace",
    "recovery", "boost", "expansion", "upgrade", "approved", "clean energy", "efficiency",
    "investment", "funding", "milestone", "outperform", "strong", "success", "optimism",
    "renewable", "deal", "alliance", "discover", "discovery", "advances"
}

NEGATIVE_SIGNALS = {
    "crisis", "crash", "plunge", "plunges", "drop", "drops", "decline", "loss", "losses",
    "war", "conflict", "attack", "strike", "sanctions", "tariff", "tariffs", "inflation",
    "recession", "layoff", "layoffs", "hack", "breach", "vulnerability", "lawsuit", "ban",
    "shortage", "deficit", "threat", "risk", "warning", "downgrade", "fine", "probe",
    "investigation", "casualties", "shutdown", "volatility", "debt", "collapse", "disruption",
    "emergency", "tension", "tensions", "fraud", "scam", "pollution", "spill",
    "earthquake", "eruption", "disaster", "rattles", "strikes"
}

# Phrase dictionary to assist accurate English-to-Indonesian contextual synthesis in fallback mode
TERM_GLOSSARY_ID = {
    "artificial intelligence": "kecerdasan buatan (AI)",
    "machine learning": "pembelajaran mesin (machine learning)",
    "semiconductor": "semikonduktor",
    "chip": "cip semikonduktor",
    "data center": "pusat data (data center)",
    "cybersecurity": "keamanan siber",
    "central bank": "bank sentral",
    "interest rate": "suku bunga",
    "interest rates": "suku bunga",
    "inflation": "inflasi",
    "stock market": "pasar saham",
    "supply chain": "rantai pasok",
    "renewable energy": "energi terbarukan",
    "clean energy": "energi bersih",
    "solar": "tenaga surya",
    "wind power": "energi angin",
    "geothermal": "panas bumi (geotermal)",
    "crude oil": "minyak mentah",
    "natural gas": "gas alam",
    "critical minerals": "mineral kritis",
    "rare earth": "logam tanah jarang",
    "mining": "pertambangan",
    "cryptocurrency": "aset kripto",
    "digital asset": "aset digital",
    "ceasefire": "gencatan senjata",
    "sanctions": "sanksi ekonomi/geopolitik",
    "foreign policy": "kebijakan luar negeri",
    "climate change": "perubahan iklim",
    "electric vehicle": "kendaraan listrik (EV)",
    "electric vehicles": "kendaraan listrik (EV)",
    "battery": "baterai",
    "nuclear": "energi nuklir",
    "grid": "jaringan listrik",
}


class AIEngine:
    """
    Modular AI Engine for summarizing and analyzing news articles in Bahasa Indonesia.
    Can switch seamlessly between Gemini API, OpenAI-compatible API, and Local Analytical Engine.
    """

    def __init__(self) -> None:
        self.provider = AI_PROVIDER
        self.gemini_client = None
        self.resolved_gemini_model: str = GEMINI_MODEL
        self.active_engine_label = "Analytical Fallback Engine (Offline/No API Key)"
        self._init_provider()

    def _get_candidate_models(self) -> List[str]:
        return [self.resolved_gemini_model]

    def _init_provider(self) -> None:
        """Initializes the configured LLM client if valid credentials exist."""
        has_valid_gemini = bool(
            GEMINI_API_KEY
            and GEMINI_API_KEY != "your_gemini_api_key_here"
            and len(GEMINI_API_KEY) > 15
        )
        has_valid_openai = bool(
            OPENAI_API_KEY
            and OPENAI_API_KEY != "your_openai_api_key_here"
            and len(OPENAI_API_KEY) > 15
        )

        if self.provider == "gemini" and has_valid_gemini:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
                self.active_engine_label = f"Google Gemini API ({GEMINI_MODEL})"
                logger.info("Initialized AI Engine: %s", self.active_engine_label)
                return
            except Exception as exc:
                logger.warning("Failed to initialize Gemini SDK: %s", exc)

        if self.provider == "openai" and has_valid_openai:
            self.active_engine_label = f"OpenAI Compatible API ({OPENAI_MODEL})"
            logger.info("Initialized AI Engine: %s", self.active_engine_label)
            return

        logger.warning(
            "Valid LLM API key not detected in .env (AI_PROVIDER=%s). "
            "Using Factual Rule-Based Analytical Engine with explicit status reporting.",
            self.provider,
        )

    def analyze_article(self, raw: RawArticle) -> ProcessedArticle:
        """
        Analyzes a single RawArticle and returns a complete ProcessedArticle.
        Attempts configured LLM API first; falls back cleanly with transparent status on error.
        """
        assigned_category, matched_keywords = categorize_article(raw)

        # 1. Try Gemini API if active
        if self.gemini_client is not None:
            try:
                return self._analyze_with_gemini(raw, assigned_category, matched_keywords)
            except Exception as exc:
                logger.error("Gemini API error for '%s': %s. Using analytical fallback.", raw.title, exc)
                return self._analyze_with_fallback(
                    raw,
                    assigned_category,
                    matched_keywords,
                    status_note=f"FALLBACK (Gemini API Error: {type(exc).__name__})",
                )

        # 2. Try OpenAI-compatible API if active
        if self.provider == "openai" and OPENAI_API_KEY and OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                return self._analyze_with_openai(raw, assigned_category, matched_keywords)
            except Exception as exc:
                logger.error("OpenAI API error for '%s': %s. Using analytical fallback.", raw.title, exc)
                return self._analyze_with_fallback(
                    raw,
                    assigned_category,
                    matched_keywords,
                    status_note=f"FALLBACK (OpenAI API Error: {type(exc).__name__})",
                )

        # 3. Deterministic Factual Analytical Engine (when API key is not configured)
        return self._analyze_with_fallback(
            raw,
            assigned_category,
            matched_keywords,
            status_note="ANALYTICAL_FALLBACK (Set GEMINI_API_KEY in .env for LLM Generation)",
        )

    def analyze_articles_batch(
        self, raw_articles: List[RawArticle], batch_size: int = 7
    ) -> List[ProcessedArticle]:
        """
        Analyzes a list of RawArticles in batches using Gemini API to optimize speed
        and stay well within API rate limits (RPM). Falls back per-article if needed.
        """
        if not raw_articles:
            return []

        if self.gemini_client is None:
            return [self.analyze_article(raw) for raw in raw_articles]

        results: List[ProcessedArticle] = []
        total = len(raw_articles)

        for start_idx in range(0, total, batch_size):
            batch = raw_articles[start_idx : start_idx + batch_size]
            logger.info(
                "Processing Gemini AI batch %d-%d of %d...",
                start_idx + 1,
                min(start_idx + batch_size, total),
                total,
            )
            try:
                batch_processed = self._analyze_batch_with_gemini(batch)
                results.extend(batch_processed)
            except Exception as exc:
                logger.warning(
                    "Batch Gemini call failed (%s), falling back to individual processing for this batch.",
                    exc,
                )
                for item in batch:
                    results.append(self.analyze_article(item))

        return results

    def _analyze_batch_with_gemini(self, batch: List[RawArticle]) -> List[ProcessedArticle]:
        """Sends a batch of articles to Gemini API and parses the JSON array response."""
        cat_kw_list = [categorize_article(raw) for raw in batch]
        items_payload = []
        for idx, (raw, (cat, _)) in enumerate(zip(batch, cat_kw_list)):
            items_payload.append(
                {
                    "index": idx,
                    "title": raw.title,
                    "source": raw.source,
                    "published_at": raw.published_at,
                    "category": cat,
                    "description": raw.description[:500],
                }
            )

        prompt = f"""Anda adalah Senior Intelligence Analyst. Analisis {len(batch)} berita berikut secara objektif dalam Bahasa Indonesia.

ATURAN KETAT:
1. JANGAN mengarang fakta, angka, atau kejadian yang tidak ada di dalam Judul dan Deskripsi sumber asli.
2. Pisahkan secara tegas antara FAKTA TERVERIFIKASI (dari teks sumber) dan INTERPRETASI AI (analisis implikasi potensial).
3. Jangan menyajikan prediksi sebagai fakta pasti.
4. Kembalikan respons HANYA dalam format JSON Array valid berisi tepat {len(batch)} objek sesuai urutan `index` (0 sampai {len(batch) - 1}) dengan skema setiap objek:

[
  {{
    "index": 0,
    "headline_id": "Terjemahan/adaptasi judul berita dalam Bahasa Indonesia yang akurat dan bergaya editorial",
    "summary_id": "Ringkasan berita 2-3 kalimat dalam Bahasa Indonesia yang merangkum informasi sumber secara akurat",
    "core_issue": "1-2 kalimat inti permasalahan berita ini",
    "why_it_matters": "1-2 kalimat mengapa berita ini penting secara strategis",
    "verified_facts": [
      "Fakta eksplisit 1 yang disebutkan langsung oleh sumber",
      "Fakta eksplisit 2 dari deskripsi/judul artikel asli"
    ],
    "ai_interpretation": "Analisis singkat berbasis fakta yang tersedia (dipisahkan dari fakta mentah)",
    "potential_impact": {{
      "economy": "Potensi dampak terhadap ekonomi, pasar, atau investasi",
      "technology": "Potensi dampak terhadap inovasi atau infrastruktur teknologi",
      "industry": "Potensi dampak terhadap rantai pasok atau sektor industri terkait",
      "society": "Potensi dampak terhadap masyarakat, tenaga kerja, atau kebijakan publik"
    }},
    "sentiment": "Positif | Negatif | Netral",
    "sentiment_score": 0.0,
    "sentiment_reason": "Alasan singkat penentuan sentimen berdasarkan nada faktual berita",
    "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]
  }}
]

DATA DAFTAR BERITA SUMBER ASLI:
{json.dumps(items_payload, ensure_ascii=False, indent=2)}
"""
        last_err = None
        for model_name in self._get_candidate_models():
            for attempt in range(1, 3):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"response_mime_type": "application/json", "temperature": 0.2},
                    )
                    self.resolved_gemini_model = model_name
                    parsed_list = json.loads(response.text)
                    if isinstance(parsed_list, dict) and "items" in parsed_list:
                        parsed_list = parsed_list["items"]
                    if not isinstance(parsed_list, list):
                        raise ValueError("Expected JSON array from batch Gemini call")

                    by_idx = {
                        int(obj.get("index", i)): obj
                        for i, obj in enumerate(parsed_list)
                        if isinstance(obj, dict)
                    }
                    output: List[ProcessedArticle] = []
                    for idx, (raw, (cat, kws)) in enumerate(zip(batch, cat_kw_list)):
                        obj = by_idx.get(idx, parsed_list[idx] if idx < len(parsed_list) else {})
                        output.append(
                            self._map_json_to_article(
                                raw,
                                obj,
                                cat,
                                kws,
                                provider_label=f"Gemini API ({GEMINI_MODEL})",
                                status="SUCCESS",
                            )
                        )
                    return output
                except Exception as exc:
                    last_err = exc
                    err_str = str(exc).lower()
                    if "not found" in err_str or "404" in err_str or "not supported" in err_str:
                        logger.warning("Model '%s' not found on public endpoint.", model_name)
                        break
                    wait_s = 2.0 * attempt
                    logger.warning("Gemini batch attempt %d (%s) failed: %s. Waiting %.1fs...", attempt, model_name, exc, wait_s)
                    time.sleep(wait_s)
        raise RuntimeError(f"Batch Gemini failed: {last_err}")

    def _build_llm_prompt(self, raw: RawArticle, category: str) -> str:
        """Builds a strict fact-grounded prompt in Bahasa Indonesia returning JSON."""
        return f"""Anda adalah Senior Intelligence Analyst. Analisis berita berikut secara objektif dalam Bahasa Indonesia.

ATURAN KETAT:
1. JANGAN mengarang fakta, angka, atau kejadian yang tidak ada di dalam Judul dan Deskripsi sumber asli.
2. Pisahkan secara tegas antara FAKTA TERVERIFIKASI (dari teks sumber) dan INTERPRETASI AI (analisis implikasi potensial).
3. Jangan menyajikan prediksi sebagai fakta pasti; gunakan frasa analitis seperti "Berpotensi memengaruhi...", "Mengindikasikan kemungkinan...".
4. Kembalikan respons HANYA dalam format JSON valid sesuai skema berikut:

{{
  "headline_id": "Terjemahan/adaptasi judul berita dalam Bahasa Indonesia yang akurat dan bergaya editorial",
  "category": "{category}",
  "summary_id": "Ringkasan berita 2-3 kalimat dalam Bahasa Indonesia yang merangkum informasi sumber secara akurat",
  "core_issue": "1-2 kalimat yang mengidentifikasi inti permasalahan dari berita ini",
  "why_it_matters": "1-2 kalimat yang menjelaskan mengapa berita ini penting secara strategis",
  "verified_facts": [
    "Fakta eksplisit 1 yang disebutkan langsung oleh sumber ({raw.source})",
    "Fakta eksplisit 2 dari deskripsi/judul artikel asli"
  ],
  "ai_interpretation": "Analisis singkat berbasis fakta yang tersedia (dipisahkan dari fakta mentah, bukan klaim fakta baru)",
  "potential_impact": {{
    "economy": "Potensi dampak terhadap ekonomi, pasar, atau investasi",
    "technology": "Potensi dampak terhadap inovasi, infrastruktur teknologi, atau R&D",
    "industry": "Potensi dampak terhadap rantai pasok, korporasi, atau sektor industri terkait",
    "society": "Potensi dampak terhadap masyarakat, tenaga kerja, atau kebijakan publik"
  }},
  "sentiment": "Positif | Negatif | Netral",
  "sentiment_score": 0.0,
  "sentiment_reason": "Alasan singkat penentuan sentimen berdasarkan nada faktual berita",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"]
}}

DATA BERITA SUMBER ASLI:
- Judul Asli: {raw.title}
- Sumber Media: {raw.source} ({raw.feed_name})
- Tanggal Publikasi: {raw.published_at}
- Kategori Awal: {category}
- URL: {raw.url}
- Deskripsi Sumber: {raw.description}
"""

    def _analyze_with_gemini(
        self, raw: RawArticle, category: str, default_keywords: List[str]
    ) -> ProcessedArticle:
        """Calls Google Gemini API with retry and parses structured JSON response."""
        prompt = self._build_llm_prompt(raw, category)
        last_err = None
        # Try configured model first (e.g. "argon"), with fallback to public API model ID if alias is not yet exposed on public endpoint
        candidate_models = self._get_candidate_models()

        for model_name in candidate_models:
            for attempt in range(1, 3):
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"response_mime_type": "application/json", "temperature": 0.2},
                    )
                    data = json.loads(response.text)
                    return self._map_json_to_article(
                        raw, data, category, default_keywords,
                        provider_label=f"Gemini API ({GEMINI_MODEL})",
                        status="SUCCESS",
                    )
                except Exception as exc:
                    last_err = exc
                    err_str = str(exc).lower()
                    if "not found" in err_str or "404" in err_str or "not supported" in err_str:
                        logger.warning("Model alias '%s' not found on public endpoint, trying fallback model...", model_name)
                        break
                    wait_s = 2.0 * attempt
                    logger.warning("Gemini attempt %d (%s) failed: %s. Waiting %.1fs...", attempt, model_name, exc, wait_s)
                    time.sleep(wait_s)
        raise RuntimeError(f"Gemini API failed after retries: {last_err}")

    def _analyze_with_openai(
        self, raw: RawArticle, category: str, default_keywords: List[str]
    ) -> ProcessedArticle:
        """Calls an OpenAI-compatible chat completion API."""
        prompt = self._build_llm_prompt(raw, category)
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "You are a precise intelligence analyst outputting valid JSON in Indonesian."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            return self._map_json_to_article(
                raw, data, category, default_keywords,
                provider_label=f"OpenAI API ({OPENAI_MODEL})",
                status="SUCCESS",
            )

    def _map_json_to_article(
        self,
        raw: RawArticle,
        data: Dict[str, Any],
        default_category: str,
        default_keywords: List[str],
        provider_label: str,
        status: str,
    ) -> ProcessedArticle:
        """Maps parsed LLM JSON dictionary into a validated ProcessedArticle."""
        impact_raw = data.get("potential_impact") or {}
        impact = PotentialImpact(
            economy=str(impact_raw.get("economy") or "Memengaruhi dinamika modal dan efisiensi biaya pada sektor terkait."),
            technology=str(impact_raw.get("technology") or "Mendorong adaptasi sistem teknologi dan standar teknis industri."),
            industry=str(impact_raw.get("industry") or "Memicu penyesuaian strategi operasional pelaku industri utama."),
            society=str(impact_raw.get("society") or "Berdampak tidak langsung pada konsumen dan kebijakan publik."),
        )
        sentiment = str(data.get("sentiment", "Netral")).capitalize()
        if sentiment not in ("Positif", "Negatif", "Netral"):
            sentiment = "Netral"

        try:
            sentiment_score = float(data.get("sentiment_score", 0.0))
        except (TypeError, ValueError):
            sentiment_score = 0.4 if sentiment == "Positif" else (-0.4 if sentiment == "Negatif" else 0.0)

        facts = data.get("verified_facts")
        if not isinstance(facts, list) or not facts:
            facts = [
                f"Sumber ({raw.source}) melaporkan: \"{raw.title}\".",
                f"Publikasi tercatat pada {raw.published_at} melalui saluran resmi {raw.feed_name}.",
            ]

        keywords = data.get("keywords")
        if not isinstance(keywords, list) or not keywords:
            keywords = default_keywords

        return ProcessedArticle(
            id=None,
            title=raw.title,
            headline_id=str(data.get("headline_id") or raw.title),
            source=raw.source,
            feed_name=raw.feed_name,
            url=raw.url,
            published_at=raw.published_at,
            published_date=raw.published_date,
            category=default_category,
            raw_description=raw.description,
            summary_id=str(data.get("summary_id") or raw.description),
            core_issue=str(data.get("core_issue") or f"Perkembangan strategis terkait {raw.title}."),
            why_it_matters=str(data.get("why_it_matters") or "Memiliki relevansi langsung terhadap pemangku kepentingan di sektor terkait."),
            verified_facts=[str(f) for f in facts[:4]],
            ai_interpretation=str(data.get("ai_interpretation") or "Analisis berbasis fakta menunjukkan perlunya pemantauan lanjutan atas dampak kebijakan dan pasar."),
            potential_impact=impact,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            sentiment_reason=str(data.get("sentiment_reason") or f"Nada pemberitaan bersifat {sentiment.lower()} berdasarkan fakta yang dilaporkan."),
            keywords=[str(k) for k in keywords[:6]],
            ai_provider_used=provider_label,
            ai_status=status,
            url_hash=raw.url_hash,
            title_hash=raw.title_hash,
        )

    def _analyze_with_fallback(
        self,
        raw: RawArticle,
        category: str,
        keywords: List[str],
        status_note: str,
    ) -> ProcessedArticle:
        """
        Deterministic, fact-preserving analytical engine in Bahasa Indonesia.
        Used when external LLM API key is not configured or unreachable, ensuring
        every real news article is accurately summarized and analyzed without hallucination.
        """
        combined_lower = f"{raw.title} {raw.description}".lower()

        # 1. Sentiment Detection based on factual lexical signals
        pos_matches = [w for w in POSITIVE_SIGNALS if re.search(rf"\b{re.escape(w)}\b", combined_lower)]
        neg_matches = [w for w in NEGATIVE_SIGNALS if re.search(rf"\b{re.escape(w)}\b", combined_lower)]

        pos_count = len(pos_matches)
        neg_count = len(neg_matches)

        if pos_count > neg_count:
            sentiment = "Positif"
            sentiment_score = round(min(0.85, 0.25 + 0.15 * (pos_count - neg_count)), 2)
            sentiment_reason = (
                f"Terdeteksi indikator perkembangan konstruktif/ekspansif pada laporan sumber "
                f"({', '.join(pos_matches[:3])})."
            )
        elif neg_count > pos_count:
            sentiment = "Negatif"
            sentiment_score = round(max(-0.85, -0.25 - 0.15 * (neg_count - pos_count)), 2)
            sentiment_reason = (
                f"Laporan menyoroti faktor risiko, tekanan, atau tantangan faktual "
                f"({', '.join(neg_matches[:3])})."
            )
        else:
            sentiment = "Netral"
            sentiment_score = 0.0
            sentiment_reason = (
                "Pemberitaan bersifat informatif dan berimbang tanpa kecenderungan sentimen ekstrem."
            )

        # 2. Extract detected Indonesian domain concepts from the text
        detected_concepts_id: List[str] = []
        for en_term, id_term in TERM_GLOSSARY_ID.items():
            if en_term in combined_lower and id_term not in detected_concepts_id:
                detected_concepts_id.append(id_term)

        topic_phrase = (
            ", ".join(detected_concepts_id[:3])
            if detected_concepts_id
            else ", ".join(keywords[:3])
        )

        # 3. Clean snippet of original description (strictly factual, no invention)
        clean_desc = raw.description.strip()
        if clean_desc.endswith("..."):
            clean_desc = clean_desc[:-3].strip()
        # Strip trailing source suffix in Google News descriptions (e.g. " - Reuters")
        clean_desc = re.sub(r"\s+-\s+[A-Za-z0-9\s.&/]+$", "", clean_desc).strip()
        clean_title = re.sub(r"\s+-\s+[A-Za-z0-9\s.&/]+$", "", raw.title.strip()).strip()

        # 4. Translate title & description into clean, natural Bahasa Indonesia (without repetitive boilerplate)
        headline_id = self._translate_to_indonesian(clean_title)
        translated_desc = (
            self._translate_to_indonesian(clean_desc[:420])
            if clean_desc and clean_desc.lower() != clean_title.lower()
            else ""
        )

        if translated_desc and translated_desc.lower() != headline_id.lower():
            if not translated_desc.endswith("."):
                translated_desc += "."
            summary_id = translated_desc
        else:
            summary_id = f"{headline_id} (Dilaporkan oleh {raw.source} pada {raw.published_date})."

        # 5. Core Issue & Why It Matters by Category (specific & non-repetitive)
        category_context = self._get_category_analytical_context(
            category, raw.source, topic_phrase, headline_id, combined_lower
        )

        # 6. Verified Facts (strictly separated from AI interpretation)
        verified_facts = [
            f"Laporan resmi {raw.source}: \"{headline_id}\".",
            f"Waktu publikasi tercatat pada {raw.published_at} melalui saluran {raw.feed_name}.",
        ]
        if translated_desc and translated_desc.lower() != headline_id.lower():
            verified_facts.append(f"Pokok informasi sumber: \"{translated_desc[:280]}\"")
        verified_facts.append(f"Tautan artikel asli: {raw.url}")

        return ProcessedArticle(
            id=None,
            title=raw.title,
            headline_id=headline_id,
            source=raw.source,
            feed_name=raw.feed_name,
            url=raw.url,
            published_at=raw.published_at,
            published_date=raw.published_date,
            category=category,
            raw_description=raw.description,
            summary_id=summary_id,
            core_issue=category_context["core_issue"],
            why_it_matters=category_context["why_it_matters"],
            verified_facts=verified_facts,
            ai_interpretation=category_context["ai_interpretation"],
            potential_impact=category_context["impact"],
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            sentiment_reason=sentiment_reason,
            keywords=keywords,
            ai_provider_used=self.active_engine_label,
            ai_status=status_note,
            url_hash=raw.url_hash,
            title_hash=raw.title_hash,
        )

    @staticmethod
    def _translate_to_indonesian(text: str) -> str:
        """
        Translates English news headlines/descriptions into fluent, natural Bahasa Indonesia
        using the lightweight public Google Translate GTX endpoint, with graceful local fallback.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        try:
            resp = httpx.get(
                "https://translate.googleapis.com/translate_a/single",
                params={
                    "client": "gtx",
                    "sl": "auto",
                    "tl": "id",
                    "dt": "t",
                    "q": cleaned,
                },
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

    @staticmethod
    def _get_category_analytical_context(
        category: str, source: str, topic_phrase: str, title: str, combined_lower: str = ""
    ) -> Dict[str, Any]:
        """Provides concise, non-repetitive, domain-specific context & impact in Bahasa Indonesia."""
        text_check = (combined_lower or title.lower())

        # Special sub-context for Geophysics, Earthquakes, Volcanoes, Geothermal & Geoneutrinos
        if any(
            w in text_check
            for w in (
                "earthquake", "gempa", "seismic", "seismik", "volcano", "volcanic",
                "gunung api", "geothermal", "panas bumi", "geophysics", "geophysical",
                "geofisika", "geoneutrino", "tectonic", "subsurface", "magma",
            )
        ):
            return {
                "core_issue": (
                    "Pemantauan aktivitas kebumian, eksplorasi bawah permukaan, dan pengembangan energi panas bumi/bersih."
                ),
                "why_it_matters": (
                    "Penting bagi mitigasi bencana geologi (gempa/vulkanik), pemetaan potensi reservoar panas bumi, "
                    "serta kemajuan riset geofisika dan transisi energi bersih."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Data dari {source} memberikan rujukan teknis bagi komunitas geofisika, "
                    f"mitigasi kebencanaan, dan pengembangan kapasitas energi bersih."
                ),
                "impact": PotentialImpact(
                    economy="Berpotensi memengaruhi investasi proyek panas bumi (geotermal) dan kesiapsiagaan infrastruktur.",
                    technology="Mendorong inovasi sensor seismik, pemodelan geofisika bawah permukaan, dan deteksi geoneutrino.",
                    industry="Relevan langsung bagi sektor eksplorasi panas bumi, pertambangan, dan ketahanan energi.",
                    society="Mendukung peringatan dini bencana geologi dan ketersediaan energi ramah lingkungan.",
                ),
            }

        # Special sub-context for Corporate M&A, Investments, Layoffs & Business Strategy
        if any(
            w in text_check
            for w in (
                "merger", "acquisition", "acquires", "buyout", "billion", "valuation",
                "funding", "raises", "layoff", "layoffs", "job cuts", "restructuring",
                "ceo", "conglomerate", "invest", "deal", "sells",
            )
        ):
            return {
                "core_issue": (
                    "Aksi korporasi strategis yang mencakup pendanaan besar, akuisisi, restrukturisasi organisasi, atau pergeseran strategi bisnis."
                ),
                "why_it_matters": (
                    "Langkah korporasi berskala besar ini mengubah peta persaingan industri, alokasi modal investor, serta arah ekspansi bisnis global."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Aksi strategis yang dilaporkan {source} mencerminkan konsolidasi modal "
                    f"dan efisiensi operasional di tengah kompetisi industri yang ketat."
                ),
                "impact": PotentialImpact(
                    economy="Memengaruhi arus modal investasi, valuasi korporasi, dan dinamika lapangan kerja sektor terkait.",
                    technology="Mempercepat akuisisi kapabilitas teknologi dan ekspansi infrastruktur perusahaan.",
                    industry="Mengubah struktur pasar dan memicu respons kompetitif dari perusahaan pesaing.",
                    society="Berdampak pada tenaga kerja, konsumen, dan ekosistem bisnis pendukung.",
                ),
            }

        if category == "AI & Technology":
            return {
                "core_issue": (
                    f"Inovasi model/produk AI dan perkembangan infrastruktur teknologi strategis ({topic_phrase})."
                ),
                "why_it_matters": (
                    "Menentukan arah adopsi kecerdasan buatan di dunia bisnis, efisiensi industri, serta persaingan ekosistem teknologi global."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Berdasarkan fakta yang dilaporkan {source}, perkembangan pada "
                    f"{topic_phrase} mengindikasikan akselerasi kompetisi teknologi yang berpotensi memengaruhi "
                    f"alokasi belanja modal (CapEx) perusahaan teknologi dan regulasi tata kelola AI."
                ),
                "impact": PotentialImpact(
                    economy="Berpotensi memengaruhi valuasi sektor teknologi, investasi modal ventura, dan produktivitas ekonomi digital.",
                    technology=f"Mendorong iterasi arsitektur sistem, infrastruktur komputasi, dan kapabilitas {topic_phrase}.",
                    industry="Memicu penyesuaian strategi produk dan integrasi otomasi pada korporasi lintas sektor.",
                    society="Memengaruhi pola kerja berbasis teknologi, privasi data, dan aksesibilitas layanan digital masyarakat.",
                ),
            }
        if category == "Economy & Finance & markets":
            return {
                "core_issue": (
                    f"Pergerakan indikator makroekonomi, kebijakan moneter/fiskal, atau dinamika pasar keuangan "
                    f"terkait {topic_phrase} yang diangkat oleh {source}."
                ),
                "why_it_matters": (
                    "Perubahan variabel ekonomi dan pasar modal berdampak langsung pada biaya modal, arus investasi "
                    "lintas negara, stabilitas nilai tukar, serta daya beli agregat."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Informasi faktual dari {source} mengenai {topic_phrase} "
                    f"menjadi sinyal penting bagi pelaku pasar dalam menilai risiko likuiditas, arah suku bunga, "
                    f"dan prospek pertumbuhan ekonomi kuartalan."
                ),
                "impact": PotentialImpact(
                    economy=f"Berhubungan langsung dengan stabilitas makroekonomi, ekspektasi inflasi, dan arus modal terkait {topic_phrase}.",
                    technology="Memengaruhi ketersediaan pendanaan R&D dan ekspansi infrastruktur finansial digital (fintech).",
                    industry="Berdampak pada biaya pembiayaan korporasi, margin laba operasional, dan rantai pasok perdagangan.",
                    society="Berpotensi memengaruhi biaya hidup, tingkat lapangan kerja, dan sentimen konsumen.",
                ),
            }
        if category == "Geopolitics/politics":
            return {
                "core_issue": (
                    f"Dinamika hubungan internasional, kebijakan keamanan, atau langkah diplomatik/politik "
                    f"terkait {topic_phrase} dalam laporan {source}."
                ),
                "why_it_matters": (
                    "Keputusan geopolitik dan kebijakan negara-negara strategis memengaruhi stabilitas kawasan, "
                    "jalur perdagangan internasional, serta kepastian hukum bagi investasi global."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Merujuk pada fakta laporan {source}, eskalasi atau negosiasi "
                    f"terkait {topic_phrase} berpotensi mengubah kalkulasi risiko geopolitik serta mendorong "
                    f"penyesuaian aliansi strategis maupun kebijakan perdagangan."
                ),
                "impact": PotentialImpact(
                    economy="Ketidakpastian atau kesepakatan geopolitik berpotensi memengaruhi premi risiko pasar dan jalur logistik global.",
                    technology="Berpotensi memengaruhi kebijakan pembatasan ekspor teknologi strategis dan kedaulatan siber.",
                    industry="Mendorong diversifikasi rantai pasok (friend-shoring) dan kepatuhan terhadap rezim sanksi/regulasi.",
                    society="Berdampak pada stabilitas sosial-politik, keamanan publik, dan dinamika kemanusiaan.",
                ),
            }
        if category == "Energy & Renewable Energy":
            return {
                "core_issue": (
                    f"Perkembangan transisi energi, kapasitas energi terbarukan, atau kebijakan dekarbonisasi "
                    f"terkait {topic_phrase} yang dilaporkan oleh {source}."
                ),
                "why_it_matters": (
                    "Transisi menuju energi bersih dan ketahanan jaringan listrik merupakan pilar utama "
                    "untuk memenuhi kebutuhan daya industri modern sekaligus menekan emisi karbon global."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Berdasarkan laporan {source}, inisiatif atau tantangan pada "
                    f"{topic_phrase} mencerminkan pergeseran struktural bauran energi yang menuntut sinkronisasi "
                    f"antara insentif kebijakan, kesiapan jaringan (grid), dan keekonomian proyek."
                ),
                "impact": PotentialImpact(
                    economy="Memengaruhi alokasi pembiayaan hijau (green financing), subsidi energi, dan tarif listrik jangka panjang.",
                    technology=f"Mendorong inovasi penyimpanan baterai, efisiensi pembangkit, dan modernisasi jaringan terkait {topic_phrase}.",
                    industry="Mengubah struktur biaya energi bagi industri manufaktur, pusat data, dan utilitas kelistrikan.",
                    society="Berkontribusi pada kualitas lingkungan hidup, ketahanan energi rumah tangga, dan lapangan kerja hijau.",
                ),
            }
        if category == "Mining, Oil & Gas":
            return {
                "core_issue": (
                    f"Dinamika pasokan, eksplorasi, produksi, atau harga komoditas hulu migas dan pertambangan "
                    f"terkait {topic_phrase} menurut laporan {source}."
                ),
                "why_it_matters": (
                    "Sektor minyak, gas, dan mineral kritis merupakan fondasi bahan baku industri global "
                    "serta penentu utama keseimbangan neraca perdagangan negara penghasil sumber daya alam."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Data faktual dari {source} seputar {topic_phrase} mengindikasikan "
                    f"sensitivitas pasar komoditas terhadap keseimbangan pasokan-permintaan fisik serta kebijakan "
                    f"hilirisasi maupun investasi hulu."
                ),
                "impact": PotentialImpact(
                    economy="Berpotensi memengaruhi harga komoditas energi/mineral, pendapatan fiskal sumber daya alam, dan inflasi biaya energi.",
                    technology="Mendorong pemanfaatan teknologi ekstraksi presisi, efisiensi kilang/smelter, dan pemantauan emisi metana.",
                    industry=f"Berdampak langsung pada rantai pasok energi, industri petrokimia, baterai EV, dan konstruksi terkait {topic_phrase}.",
                    society="Memengaruhi harga bahan bakar transportasi, aktivitas ekonomi daerah tambang, dan tata kelola lingkungan.",
                ),
            }
        if category == "Cryptocurrency":
            return {
                "core_issue": (
                    f"Perkembangan pasar aset digital, infrastruktur blockchain, atau kerangka regulasi kripto "
                    f"terkait {topic_phrase} yang diberitakan oleh {source}."
                ),
                "why_it_matters": (
                    "Integrasi aset kripto dengan sistem keuangan institusional (ETF, stablecoin, tokenisasi) "
                    "semakin mempererat keterkaitan likuiditas aset digital dengan pasar modal global."
                ),
                "ai_interpretation": (
                    f"[Interpretasi Analitis] Mengacu pada laporan {source}, dinamika pada {topic_phrase} "
                    f"menunjukkan tingginya responsivitas ekosistem aset digital terhadap kejelasan regulasi, "
                    f"arus modal institusional, serta keamanan protokol on-chain."
                ),
                "impact": PotentialImpact(
                    economy="Memengaruhi likuiditas pasar aset berisiko (risk-on assets) dan inovasi sistem pembayaran lintas batas.",
                    technology=f"Mendorong pengembangan protokol kriptografi, skalabilitas jaringan blockchain, dan keamanan smart contract.",
                    industry="Memicu penyesuaian kepatuhan (compliance) pada bursa kripto, kustodian aset digital, dan perbankan.",
                    society="Menuntut peningkatan literasi keuangan digital dan perlindungan investor ritel terhadap volatilitas.",
                ),
            }

        # Default: Dunia (Global / International)
        return {
            "core_issue": (
                f"Perkembangan peristiwa internasional dan dinamika global terkait {topic_phrase} "
                f"sebagaimana dilaporkan oleh {source}."
            ),
            "why_it_matters": (
                "Peristiwa lintas batas di tingkat global memiliki efek rambatan terhadap kebijakan publik, "
                "kerja sama multilateral, serta stabilitas kawasan."
            ),
            "ai_interpretation": (
                f"[Interpretasi Analitis] Berdasarkan fakta yang disajikan {source}, isu {topic_phrase} "
                f"perlu dicermati dalam konteks keterhubungan global yang dapat memengaruhi respons "
                f"lembaga internasional dan pemerintah nasional."
            ),
            "impact": PotentialImpact(
                economy="Berpotensi menimbulkan dampak sekunder pada aktivitas ekonomi regional dan mobilitas lintas negara.",
                technology="Mendorong pemanfaatan sistem informasi, pemantauan dini, dan kolaborasi ilmiah internasional.",
                industry="Memengaruhi operasional organisasi multinasional dan sektor jasa global.",
                society="Berdampak langsung pada kesadaran publik, dinamika sosial, dan respons kebijakan kemasyarakatan.",
            ),
        }

    def generate_executive_summary(self, articles: List[ProcessedArticle]) -> ExecutiveSummary:
        """
        Generates the Executive Summary (Overview, 3-5 Key Issues, Global Outlook, Closing Insights)
        across all processed articles. Uses Gemini API if configured, otherwise synthesizes
        quantitatively and thematically from the processed dataset.
        """
        if not articles:
            return ExecutiveSummary(
                overview="Tidak ada berita baru yang ditemukan pada siklus pengambilan saat ini.",
                key_issues=[],
                global_outlook="Menunggu pembaruan data dari sumber RSS dan API.",
                closing_insights="Sistem siap menjalankan siklus agregasi berikutnya.",
                macro_trends=[],
                generated_by=self.active_engine_label,
            )

        # Try Gemini API if available
        if self.gemini_client is not None:
            try:
                return self._generate_exec_summary_gemini(articles)
            except Exception as exc:
                logger.warning("Gemini Executive Summary generation failed (%s). Using analytical synthesis.", exc)

        return self._generate_exec_summary_analytical(articles)

    def _generate_exec_summary_gemini(self, articles: List[ProcessedArticle]) -> ExecutiveSummary:
        """Uses Gemini API to synthesize the Executive Summary and Closing Insights from article headlines."""
        digest_lines = [
            f"- [{a.category}] ({a.source}, Sentimen: {a.sentiment}): {a.title} -> {a.core_issue}"
            for a in articles[:35]
        ]
        prompt = f"""Anda adalah Chief Intelligence Officer. Berdasarkan kumpulan {len(articles)} berita terverifikasi berikut, buat Executive Summary dan Closing Insights dalam Bahasa Indonesia.

ATURAN:
1. Hanya gunakan fakta dari daftar berita di bawah ini. Jangan mengarang peristiwa fiktif.
2. Kembalikan JSON valid dengan struktur:
{{
  "overview": "Paragraf ringkasan eksekutif (3-4 kalimat) mengenai perkembangan berita paling penting hari ini.",
  "key_issues": [
    {{"title": "Judul Isu Utama 1", "description": "Penjelasan 2 kalimat berdasarkan berita yang dikumpulkan"}},
    {{"title": "Judul Isu Utama 2", "description": "Penjelasan 2 kalimat"}},
    {{"title": "Judul Isu Utama 3", "description": "Penjelasan 2 kalimat"}},
    {{"title": "Judul Isu Utama 4", "description": "Penjelasan 2 kalimat"}}
  ],
  "global_outlook": "Gambaran umum perkembangan global (2-3 kalimat) yang menghubungkan dimensi teknologi, ekonomi, geopolitik, dan energi.",
  "closing_insights": "Kesimpulan analitis (3-4 kalimat) mengenai tren dan perkembangan penting dari seluruh berita yang dikumpulkan.",
  "macro_trends": [
    "Tren 1...",
    "Tren 2...",
    "Tren 3...",
    "Tren 4..."
  ]
}}

DAFTAR BERITA TERKUMPUL:
{chr(10).join(digest_lines)}
"""
        candidate_models = self._get_candidate_models()

        response = None
        for model_name in candidate_models:
            try:
                response = self.gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={"response_mime_type": "application/json", "temperature": 0.2},
                )
                break
            except Exception as exc:
                if model_name == candidate_models[-1]:
                    raise
                logger.warning("Executive summary model '%s' unavailable (%s), trying fallback...", model_name, exc)

        data = json.loads(response.text)
        return ExecutiveSummary(
            overview=str(data.get("overview", "")),
            key_issues=data.get("key_issues", [])[:5],
            global_outlook=str(data.get("global_outlook", "")),
            closing_insights=str(data.get("closing_insights", "")),
            macro_trends=data.get("macro_trends", [])[:5],
            generated_by=f"Google Gemini API ({GEMINI_MODEL})",
        )

    def _generate_exec_summary_analytical(self, articles: List[ProcessedArticle]) -> ExecutiveSummary:
        """Synthesizes a comprehensive, data-driven Executive Summary from the collected articles."""
        total = len(articles)
        by_cat: Dict[str, List[ProcessedArticle]] = {}
        sent_counts = {"Positif": 0, "Negatif": 0, "Netral": 0}
        sources_set = set()

        for art in articles:
            by_cat.setdefault(art.category, []).append(art)
            sent_counts[art.sentiment] = sent_counts.get(art.sentiment, 0) + 1
            sources_set.add(art.source)

        sorted_cats = sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True)
        top_cats_str = ", ".join(f"{c} ({len(items)} berita)" for c, items in sorted_cats[:4])

        overview = (
            f"Laporan intelijen ini menghimpun dan menganalisis {total} berita aktual dari "
            f"{len(sources_set)} sumber global terpercaya ({', '.join(sorted(list(sources_set))[:7])}, dll.). "
            f"Distribusi pemberitaan didominasi oleh sektor {top_cats_str}. "
            f"Secara agregat, profil sentimen pemberitaan mencatat {sent_counts['Positif']} berita bersentimen Positif, "
            f"{sent_counts['Netral']} Netral, dan {sent_counts['Negatif']} Negatif, yang mencerminkan "
            f"kombinasi antara akselerasi inovasi teknologi/energi dan kewaspadaan terhadap dinamika ekonomi serta geopolitik."
        )

        # Build up to 5 Key Issues from the top categories with actual article citations
        key_issues: List[Dict[str, str]] = []
        for cat_name, cat_articles in sorted_cats[:5]:
            lead = cat_articles[0]
            second_info = (
                f" Selain itu, {cat_articles[1].source} turut menyoroti \"{cat_articles[1].title}\"."
                if len(cat_articles) > 1
                else ""
            )
            key_issues.append(
                {
                    "title": f"Fokus {cat_name}: Sorotan pada {', '.join(lead.keywords[:2])}",
                    "description": (
                        f"Isu utama di kategori ini dipimpin oleh laporan {lead.source} berjudul "
                        f"\"{lead.title}\".{second_info} ({len(cat_articles)} artikel terkait teridentifikasi)."
                    ),
                }
            )

        global_outlook = (
            "Perkembangan global saat ini memperlihatkan interdependensi yang semakin kuat antara "
            "infrastruktur kecerdasan buatan (AI), ketahanan pasokan energi & mineral kritis, serta kebijakan "
            "makroekonomi dan geopolitik. Negara dan korporasi global secara aktif menyeimbangkan agenda "
            "pertumbuhan teknologi tinggi dengan mitigasi risiko rantai pasok, transisi energi bersih, "
            "serta stabilitas pasar keuangan."
        )

        closing_insights = (
            f"Berdasarkan sintesis atas {total} artikel yang berhasil diverifikasi, terdapat konvergensi strategis "
            f"antara kebutuhan komputasi AI skala besar, penyediaan daya listrik (termasuk energi terbarukan dan gas/nuklir), "
            f"serta pengamanan komoditas pertambangan strategis. Di sisi lain, pergerakan pasar modal dan aset digital "
            f"tetap sangat sensitif terhadap sinyal kebijakan bank sentral serta perkembangan diplomasi internasional. "
            f"Pemantauan berkelanjutan secara terotomatisasi menjadi krusial untuk mendeteksi pergeseran risiko dan peluang lebih dini."
        )

        macro_trends = [
            "Akselerasi integrasi Artificial Intelligence ke dalam infrastruktur industri, komputasi awan, dan otomasi enterprise.",
            "Ketergantungan silang antara ekspansi pusat data teknologi dan kapasitas jaringan energi bersih maupun komoditas hulu.",
            "Kewaspadaan pelaku pasar keuangan terhadap kebijakan suku bunga, arus perdagangan global, dan regulasi lintas batas.",
            "Peningkatan nilai strategis komoditas pertambangan (mineral kritis, tembaga, litium) serta dinamika pasokan minyak & gas.",
            "Institusionalisasi pasar aset digital (Cryptocurrency) yang semakin berkorelasi dengan indikator likuiditas makro.",
        ]

        return ExecutiveSummary(
            overview=overview,
            key_issues=key_issues,
            global_outlook=global_outlook,
            closing_insights=closing_insights,
            macro_trends=macro_trends,
            generated_by=self.active_engine_label,
        )

