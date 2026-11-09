# Personal AI News Intelligence Aggregator

Sistem otomasi end-to-end berbasis **Python**, **Feedparser**, **HTTPX**, **SQLite**, **APScheduler**, dan **Configurable AI Engine (Google Gemini API / OpenAI Compatible / Analytical Engine)** untuk mengumpulkan, memvalidasi, mengategorikan, menganalisis, dan merangkum berita global terkini ke dalam laporan **HTML5 Editorial Interaktif** bergaya portal berita profesional.

---

## 1. Fitur Utama & Keunggulan Arsitektur

- **Multi-Source Trusted Data Collection (RSS & Public API)**:
  Mengambil berita langsung secara real-time dari **Reuters**, **BBC News**, **CNBC**, **Bloomberg**, **The Guardian**, **TechCrunch**, **MIT Technology Review**, **IEEE Spectrum**, **IEA / Clean Energy**, **World Bank News API**, **Mining.com**, **OilPrice**, **CoinDesk**, dan **Cointelegraph**.
- **7 Kategori Strategis**:
  1. `AI & Technology`
  2. `Economy & Finance & markets`
  3. `Geopolitics/politics`
  4. `Energy & Renewable Energy`
  5. `Mining, Oil & Gas`
  6. `Dunia`
  7. `Cryptocurrency`
- **Deduplikasi Berlapis Berbasis SQLite**:
  Menghitung hash SHA-256 pada URL yang telah dinormalisasi (tanpa parameter pelacak `utm_*`) dan judul berita untuk memastikan tidak ada berita yang diproses berulang kali pada eksekusi terjadwal berikutnya.
- **Integrasi AI Engine yang Dapat Dikonfigurasi & Pemisahan Fakta vs Interpretasi**:
  - Mendukung **Google Gemini API (`google-genai`)** sebagai engine utama, **OpenAI-compatible API**, serta **Factual Analytical Fallback Engine** apabila API key belum dikonfigurasi atau terjadi batas kuota (rate limit).
  - Setiap kartu berita menampilkan **Ringkasan Bahasa Indonesia**, **Inti Permasalahan**, **Mengapa Berita Penting**, **Fakta Terverifikasi Sumber** (dipisahkan tegas dari **Interpretasi AI**), **Potential Impact** (Ekonomi, Teknologi, Industri, Masyarakat), **Sentiment Analysis** (`Positif`, `Negatif`, `Netral` beserta skor & alasan), serta **Keywords**.
- **Laporan HTML5 Editorial Mandiri (Self-Contained)**:
  - Menggunakan tipografi utama **Times New Roman** dengan desain light-mode bergaya publikasi intelijen/ekonomi klasik.
  - Dapat dibuka langsung melalui browser (`file://`) tanpa memerlukan server tambahan.
  - Dilengkapi **Dashboard Distribusi Kategori**, **Live Keyword Search**, **Filter Kategori**, **Filter Rentang Tanggal & Tanggal Spesifik**, **Filter Sentimen**, **Sorting Multi-Kriteria**, dan **Tombol Regenerate Report**.

---

## 2. Struktur Folder Proyek

```text
personal_ai_news_aggregator/
├── .env.example                 # Template konfigurasi environment & API Keys
├── requirements.txt             # Daftar paket dependensi Python
├── README.md                    # Dokumentasi instalasi, arsitektur, dan penggunaan
├── main.py                      # Entry point utama (CLI, APScheduler daemon, Local Trigger API)
├── config/
│   ├── __init__.py
│   └── settings.py              # Konfigurasi sumber RSS/API, kategori, kata kunci, dan timeout
├── src/
│   ├── __init__.py
│   ├── models.py                # Skema dataclass (RawArticle, ProcessedArticle, ExecutiveSummary)
│   ├── database.py              # Manajer SQLite (tabel articles & run_logs, deduplikasi)
│   ├── fetcher.py               # Pengambil RSS Feed & World Bank API + retry, timeout, sanitasi HTML
│   ├── categorizer.py           # Filter relevansi & klasifikasi multi-sinyal ke 7 kategori
│   ├── ai_engine.py             # Engine analisis AI (Gemini API, OpenAI API, Analytical Fallback)
│   ├── report_generator.py      # Generator laporan HTML5 lengkap (standalone & dated output)
│   └── scheduler.py             # Orkestrator 8-tahap workflow & APScheduler daemon
├── templates/
│   ├── report_template.html     # Template master HTML5
│   ├── styles.css               # Stylesheet CSS3 editorial (Times New Roman, Light Mode, Responsif)
│   └── app.js                   # Logika interaktif JavaScript (Search, Filter, Sort, Modal)
├── data/
│   └── news_history.db          # Database SQLite penyimpan riwayat berita & log eksekusi
├── output/
│   ├── latest_report.html       # Laporan HTML terbaru (siap dibuka langsung di browser)
│   └── news_report_YYYY-MM-DD_HHMMSS.html
└── logs/
    └── aggregator.log           # Log operasional berputar (RotatingFileHandler)
```

---

## 3. Panduan Instalasi & Konfigurasi

### Langkah 1: Siapkan Virtual Environment
```powershell
cd a:\.gemini\antigravity-ide\personal_ai_news_aggregator
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
```

### Langkah 2: Konfigurasi File `.env`
Salin `.env.example` menjadi `.env`:
```powershell
Copy-Item .env.example .env
```
Edit file `.env` dan masukkan API Key Gemini Anda (opsional namun direkomendasikan untuk generasi LLM penuh):
```ini
AI_PROVIDER=gemini
GEMINI_API_KEY=masukkan_api_key_gemini_anda_disini
GEMINI_MODEL=gemini-2.5-flash
```
> **Catatan Ketahanan (Resilience):** Jika `GEMINI_API_KEY` belum diisi atau terjadi kendala jaringan/kuota API, sistem secara otomatis mengaktifkan **Factual Analytical Fallback Engine** dan menampilkan badge status yang transparan pada setiap kartu berita tanpa menghentikan pembuatan laporan.

---

## 4. Cara Menjalankan Aplikasi

### A. Eksekusi Sekali Jalan (Manual Trigger)
Mengambil berita terbaru dari seluruh RSS/API, memproses berita baru, menyimpan ke SQLite, dan menghasilkan laporan HTML:
```powershell
.\.venv\Scripts\python.exe main.py --run-once
```

### B. Menjalankan Penjadwalan Otomatis (APScheduler Daemon)
Menjalankan agregasi otomatis setiap `N` jam (default: 6 jam):
```powershell
.\.venv\Scripts\python.exe main.py --schedule --interval-hours 6
```

### C. Menghasilkan Ulang HTML dari Database Tanpa Fetch Ulang
```powershell
.\.venv\Scripts\python.exe main.py --report-only
```

### D. Menjalankan Local Trigger Server untuk Tombol "Regenerate" di Browser
```powershell
.\.venv\Scripts\python.exe main.py --serve
```

---

## 5. Membuka Laporan HTML
Buka file berikut langsung di browser pilihan Anda (Chrome, Edge, Firefox, Safari) cukup dengan klik ganda (tanpa memerlukan web server):
- `output/latest_report.html`
- `output/news_report_YYYY-MM-DD_HHMMSS.html`
