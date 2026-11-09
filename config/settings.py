"""
Centralized configuration and RSS/API source definitions for Personal AI News Aggregator.
"""
import os
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from project .env or user ~/.env
load_dotenv(BASE_DIR / ".env")
load_dotenv(Path.home() / ".env")

# AI Configuration
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").strip().lower()
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "argon")

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Network & Fetcher Settings
HTTP_TIMEOUT_SECONDS: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
MAX_ARTICLES_PER_FEED: int = int(os.getenv("MAX_ARTICLES_PER_FEED", "6"))
MAX_TOTAL_ARTICLES_PER_RUN: int = int(os.getenv("MAX_TOTAL_ARTICLES_PER_RUN", "42"))
VERIFY_ARTICLE_URLS: bool = os.getenv("VERIFY_ARTICLE_URLS", "true").lower() == "true"

# Scheduler & Daily Notification Settings
SCHEDULE_INTERVAL_HOURS: int = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "6"))
DAILY_NOTIFICATION_TIME: str = os.getenv("DAILY_NOTIFICATION_TIME", "09:00").strip()
RUN_ON_STARTUP: bool = os.getenv("RUN_ON_STARTUP", "true").lower() == "true"

# Telegram Mobile Notification Settings (Primary - No Password Required)
ENABLE_TELEGRAM_NOTIFICATION: bool = os.getenv("ENABLE_TELEGRAM_NOTIFICATION", "true").lower() == "true"
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Gmail Mobile Notification Settings (Optional Legacy SMTP TLS)
ENABLE_GMAIL_NOTIFICATION: bool = os.getenv("ENABLE_GMAIL_NOTIFICATION", "false").lower() == "true"
GMAIL_SENDER: str = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
GMAIL_RECIPIENT: str = os.getenv("GMAIL_RECIPIENT", "")
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))

# Paths
DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/news_history.db")
OUTPUT_DIR: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
LOG_DIR: Path = BASE_DIR / "logs"
TEMPLATE_DIR: Path = BASE_DIR / "templates"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# Ensure directories exist
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Exact 7 Categories required for the HTML News Report
CATEGORIES: List[str] = [
    "AI & Technology",
    "Economy & Finance & markets",
    "Geopolitics/politics",
    "Energy & Renewable Energy",
    "Mining, Oil & Gas",
    "Dunia",
    "Cryptocurrency",
]

# Trusted RSS Feeds and Public APIs covering all required media & focus areas
TRUSTED_FEEDS: List[Dict[str, Any]] = [
    # --- AI & Technology ---
    {
        "name": "TechCrunch AI",
        "source_label": "TechCrunch",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    {
        "name": "TechCrunch Main",
        "source_label": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    {
        "name": "MIT Technology Review",
        "source_label": "MIT Technology Review",
        "url": "https://www.technologyreview.com/feed/",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    {
        "name": "IEEE Spectrum",
        "source_label": "IEEE Spectrum",
        "url": "https://spectrum.ieee.org/feeds/feed.rss",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    {
        "name": "BBC Technology",
        "source_label": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    {
        "name": "The Guardian Technology",
        "source_label": "The Guardian",
        "url": "https://www.theguardian.com/uk/technology/rss",
        "default_category": "AI & Technology",
        "type": "rss",
    },
    # --- Economy, Finance & Markets ---
    {
        "name": "Corporate M&A, Conglomerates & Strategic Investments",
        "source_label": "Reuters / Global Business",
        "url": "https://news.google.com/rss/search?q=(merger+OR+acquisition+OR+buyout+OR+%22billion+deal%22+OR+layoffs+OR+restructuring+OR+conglomerate)+when:3d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "CNBC Finance & Markets",
        "source_label": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "CNBC Global Economy",
        "source_label": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "BBC Business",
        "source_label": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "The Guardian Economics",
        "source_label": "The Guardian",
        "url": "https://www.theguardian.com/business/economics/rss",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "Bloomberg Markets (via Google News RSS)",
        "source_label": "Bloomberg",
        "url": "https://news.google.com/rss/search?q=site:bloomberg.com+economy+OR+markets+OR+energy+when:2d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Economy & Finance & markets",
        "type": "rss",
    },
    {
        "name": "World Bank News API",
        "source_label": "World Bank",
        "url": "https://search.worldbank.org/api/v2/news?format=json&rows=8&os=0",
        "default_category": "Economy & Finance & markets",
        "type": "worldbank_api",
    },
    # --- Geopolitics & International Relations / Dunia ---
    {
        "name": "Reuters World & Geopolitics (via Google News RSS)",
        "source_label": "Reuters",
        "url": "https://news.google.com/rss/search?q=site:reuters.com+world+OR+geopolitics+OR+economy+when:2d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Geopolitics/politics",
        "type": "rss",
    },
    {
        "name": "BBC World News",
        "source_label": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "default_category": "Dunia",
        "type": "rss",
    },
    {
        "name": "The Guardian World",
        "source_label": "The Guardian",
        "url": "https://www.theguardian.com/world/rss",
        "default_category": "Geopolitics/politics",
        "type": "rss",
    },
    {
        "name": "CNBC World Politics & News",
        "source_label": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
        "default_category": "Geopolitics/politics",
        "type": "rss",
    },
    # --- Energy, Renewable Energy & Geophysics (Gempa, Gunung Api, Panas Bumi, Geoneutrino) ---
    {
        "name": "Geophysics: Earthquake, Volcano, Seismic & Geoneutrino",
        "source_label": "Geophysics & Earth Watch",
        "url": "https://news.google.com/rss/search?q=(earthquake+OR+volcano+OR+%22volcanic+eruption%22+OR+seismic+OR+geophysics+OR+%22geophysical+survey%22+OR+geoneutrino)+when:7d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Energy & Renewable Energy",
        "type": "rss",
    },
    {
        "name": "Geothermal, Subsurface Geophysics & Clean Energy",
        "source_label": "Geothermal & Clean Energy",
        "url": "https://news.google.com/rss/search?q=(%22geothermal+energy%22+OR+geothermal+OR+geoneutrino+OR+%22seismic+survey%22+OR+%22clean+energy%22+OR+%22green+hydrogen%22)+when:7d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Energy & Renewable Energy",
        "type": "rss",
    },
    {
        "name": "The Guardian Energy & Renewables",
        "source_label": "The Guardian",
        "url": "https://www.theguardian.com/environment/energy/rss",
        "default_category": "Energy & Renewable Energy",
        "type": "rss",
    },
    {
        "name": "IEA & Clean Energy (via Google News RSS)",
        "source_label": "IEA / Clean Energy",
        "url": "https://news.google.com/rss/search?q=(%22International+Energy+Agency%22+OR+%22renewable+energy%22+OR+geothermal+OR+solar+OR+grid)+when:7d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Energy & Renewable Energy",
        "type": "rss",
    },
    {
        "name": "BBC Science & Environment",
        "source_label": "BBC News",
        "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "default_category": "Energy & Renewable Energy",
        "type": "rss",
    },
    # --- Mining, Oil & Gas ---
    {
        "name": "CNBC Energy, Oil & Gas",
        "source_label": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768",
        "default_category": "Mining, Oil & Gas",
        "type": "rss",
    },
    {
        "name": "OilPrice Energy & Commodities",
        "source_label": "OilPrice / Energy",
        "url": "https://oilprice.com/rss/main",
        "default_category": "Mining, Oil & Gas",
        "type": "rss",
    },
    {
        "name": "Mining.com Global Mining",
        "source_label": "Mining.com",
        "url": "https://www.mining.com/feed/",
        "default_category": "Mining, Oil & Gas",
        "type": "rss",
    },
    {
        "name": "Reuters Commodities & Energy (via Google News RSS)",
        "source_label": "Reuters",
        "url": "https://news.google.com/rss/search?q=site:reuters.com+(oil+OR+gas+OR+mining+OR+lithium+OR+nickel+OR+coal+OR+geothermal)+when:3d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "Mining, Oil & Gas",
        "type": "rss",
    },
    # --- Cryptocurrency ---
    {
        "name": "CoinDesk Digital Assets",
        "source_label": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "default_category": "Cryptocurrency",
        "type": "rss",
    },
    {
        "name": "Cointelegraph Markets",
        "source_label": "Cointelegraph",
        "url": "https://cointelegraph.com/rss",
        "default_category": "Cryptocurrency",
        "type": "rss",
    },
]

# Category classification keyword weights
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Cryptocurrency": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
        "blockchain", "stablecoin", "defi", "web3", "solana", "token",
        "coinbase", "binance", "digital asset", "crypto etf", "altcoin"
    ],
    "Mining, Oil & Gas": [
        "oil", "crude", "brent", "wti", "opec", "natural gas", "lng",
        "petroleum", "refinery", "drilling", "shale", "mining", "miner",
        "lithium", "nickel", "copper", "cobalt", "coal", "gold mine",
        "iron ore", "rare earth", "smelter", "upstream", "oilfield",
        "bauxite", "critical minerals"
    ],
    "Energy & Renewable Energy": [
        "renewable", "solar", "wind power", "wind farm", "geothermal",
        "hydropower", "green hydrogen", "clean energy", "energy transition",
        "battery storage", "grid", "nuclear power", "nuclear energy",
        "iea", "international energy agency", "decarbonization", "net zero",
        "ev charging", "carbon capture", "photovoltaic", "biofuel", "electricity",
        "geophysics", "geophysical", "geoneutrino", "seismic survey", "subsurface",
        "earthquake", "volcano", "volcanic", "seismology", "tectonic", "magma", "fusion"
    ],
    "AI & Technology": [
        "artificial intelligence", "machine learning", "llm", "generative ai",
        "openai", "gemini", "deepmind", "anthropic", "nvidia", "semiconductor",
        "chip", "quantum computing", "robotics", "cybersecurity", "cloud computing",
        "software", "startup", "data center", "neural network", "algorithm",
        "automation", "autonomous", "apple", "microsoft", "google", "meta"
    ],
    "Economy & Finance & markets": [
        "inflation", "interest rate", "central bank", "federal reserve", "fed",
        "gdp", "recession", "stock market", "wall street", "nasdaq", "s&p 500",
        "dow jones", "bond", "treasury", "yield", "imf", "world bank", "trade",
        "tariff", "fiscal", "monetary", "banking", "investment", "earnings",
        "IPO", "currency", "forex", "economic growth", "unemployment", "debt"
    ],
    "Geopolitics/politics": [
        "geopolitics", "diplomacy", "sanctions", "nato", "united nations",
        "treaty", "summit", "foreign policy", "election", "parliament",
        "congress", "white house", "kremlin", "beijing", "pentagon",
        "defense", "military", "conflict", "ceasefire", "sovereignty",
        "bilateral", "embassy", "national security", "geopolitical", "war"
    ],
    "Dunia": [
        "world", "international", "global", "society", "humanitarian",
        "climate", "disaster", "earthquake", "flood", "health", "who",
        "education", "migration", "unesco", "population", "europe",
        "asia", "middle east", "africa", "latin america"
    ],
}

