# 🏠 French Real Estate Analyzer

A comprehensive tool for scraping, evaluating, and comparing French real estate listings from SeLoger and PAP.fr.

## Features

- **Multi-Source Scraping**: Extract listing data from SeLoger.com and PAP.fr in the same command
- **Anti-Bot Bypass**: Uses `cloudscraper` to bypass Cloudflare and similar protections
- **Description Parsing**: Extract hidden information from listing descriptions (charges, metro lines, building era, etc.)
- **French Evaluation Protocol**: Score listings based on critical French real estate criteria
- **Comparison Tool**: Compare multiple listings side-by-side and find the best value
- **CSV Export**: Export comparison data for spreadsheet analysis

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd real_estate_analyzer

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `requests` + `cloudscraper` - HTTP requests with anti-bot bypass
- `httpx` - Alternative HTTP client
- `beautifulsoup4` + `lxml` - HTML parsing
- `pydantic` - Data validation
- `playwright` (optional) - Headless browser for JS-heavy pages

## Quick Start

### Compare Listings from Multiple Sources

You can compare listings from both PAP and SeLoger in the same command:

```bash
# Compare PAP and SeLoger listings side-by-side
python scripts/compare_listings.py \
  "https://www.pap.fr/annonces/appartement-montrouge-92120-r461901225" \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/253220767.htm" \
  --detailed

# Compare multiple listings with different sort options
python scripts/compare_listings.py \
  "https://www.pap.fr/annonces/appartement-paris-11e-r123456789" \
  "https://www.seloger.com/annonces/achat/appartement/paris-11/987654321.htm" \
  --sort value --export comparison.csv
```

### Analyze a Single Listing

```bash
# Scrape a PAP listing (uses requests/cloudscraper by default)
python scripts/test_scraper.py "https://www.pap.fr/annonces/appartement-montrouge-92120-r461901225"

# Scrape a SeLoger listing
python scripts/test_scraper.py "https://www.seloger.com/annonces/achat/appartement/montrouge-92/253220767.htm"

# With full evaluation report
python scripts/test_scraper.py "https://www.pap.fr/annonces/..." --evaluate

# Use headless browser for stubborn pages
python scripts/test_scraper.py "https://www.seloger.com/annonces/..." --mode headless
```

## Scraper Architecture

### Fetch Modes

| Mode | Library | Description | Best For |
|------|---------|-------------|----------|
| `requests` | cloudscraper | Bypasses Cloudflare/anti-bot | **Default** - PAP, most sites |
| `simple` | httpx | Fast, lightweight | Cached pages, testing |
| `headless` | Playwright | Full browser rendering | JS-heavy pages, captchas |

### Supported Sites

| Site | Status | Notes |
|------|--------|-------|
| **PAP.fr** | ✅ Working | Uses cloudscraper, reliable |
| **SeLoger.com** | ⚠️ Protected | Strong anti-bot (Cloudflare + CAPTCHA). Works with cached pages or headless mode |

## Evaluation Criteria

The French Real Estate Evaluation Protocol scores listings based on 5 key criteria:

| # | Criterion | Weight | Description |
|---|-----------|--------|-------------|
| 1 | **Loi Carrez** | 20% | Surface compliance and price/m² |
| 2 | **DPE Energy** | 25% | Energy rating and rental ban risk |
| 3 | **Location** | 20% | Transport access, city, neighborhood |
| 4 | **Building Health** | 20% | Copropriété charges, procedures, era |
| 5 | **Features** | 15% | Floor, orientation, amenities |

### DPE Rental Ban Schedule (France)

| DPE | Status |
|-----|--------|
| G | ❌ Banned since 2025 |
| F | ⚠️ Banned from 2028 |
| E | ⚠️ Banned from 2034 |
| A-D | ✅ No restrictions |

## Command Reference

### compare_listings.py

```bash
# Compare multiple listings from any supported source
python scripts/compare_listings.py URL1 URL2 URL3 [OPTIONS]

Options:
  -m, --mode      Fetch mode: requests, simple, headless (default: requests)
  -s, --sort      Sort by: score, price, price_m2, surface, value (default: score)
  -d, --detailed  Show detailed side-by-side comparison
  -e, --export    Export to CSV file
```

### test_scraper.py

```bash
# Scrape and display a listing
python scripts/test_scraper.py URL [OPTIONS]

Options:
  -m, --mode      Fetch mode: requests, simple, headless (default: requests)
  -e, --evaluate  Run full evaluation and show report
  -v, --verbose   Show description and raw JSON
  -c, --cached    Use cached HTML only
  -r, --refresh   Clear cache and refetch
```

## Output Example

```text
📋 LISTING COMPARISON SUMMARY
====================================================================================================
#   City            Surface    Price        €/m²       Score    Rating   Risk         DPE   Value
----------------------------------------------------------------------------------------------------
→1  Montrouge       50         435,000      8,700      89       ★★★★☆    🟢 Low        A     20.5
 2  Montrouge       56         550,000      9,821      86       ★★★★☆    🟢 Low        B     15.5
----------------------------------------------------------------------------------------------------

🔍 DETAILED COMPARISON
====================================================================================================
Metric             │ #1 Montrouge (PAP)      │ #2 Montrouge (SeLoger)
────────────────────────────────────────────────────────────────────
Price              │ 435,000€                │ 550,000€
Surface            │ 50.0m²                  │ 56.0m²
Price/m²           │ 8,700€                  │ 9,821€
DPE                │ A                       │ B
Elevator           │ ✗                       │ ✓
Parking            │ ✗                       │ ✓

💡 RECOMMENDATION
====================================================================================================
  🏆 BEST OVERALL SCORE: #1 Montrouge (Score: 89/100)
  💰 BEST VALUE: #1 Montrouge (20.5 pts per 100k€)
  💵 LOWEST PRICE: #1 Montrouge (435,000€)
  🛡️ LOWEST RISK: #1 Montrouge (🟢 Low Risk)
```

## Data Extracted

### From Structured Data

- Price, Surface, Rooms, Bedrooms
- DPE/GES Energy Rating
- City, Postal Code
- Floor, Elevator
- Property Type

### From Description Parsing

- Annual charges (Charges annuelles)
- Building era (Années 20, Haussmannien, etc.)
- Condition (No work needed, To renovate, etc.)
- Metro lines and distance
- Street name
- Copropriété info (lots, procedures)
- Interior features (parquet, fireplace, high ceilings)
- Orientation and exposure

## Project Structure

```text
real_estate_analyzer/
├── scripts/
│   ├── test_scraper.py      # Single listing analysis
│   └── compare_listings.py  # Multi-listing comparison
├── src/
│   ├── scraper/
│   │   ├── base.py          # Core scraping infrastructure
│   │   │                    # - CacheManager: HTML caching
│   │   │                    # - RequestsClient: cloudscraper-based HTTP
│   │   │                    # - HTTPClient: httpx-based HTTP
│   │   │                    # - HeadlessBrowserClient: Playwright
│   │   │                    # - DescriptionParser: Extract info from text
│   │   ├── seloger.py       # SeLoger.com scraper
│   │   └── pap.py           # PAP.fr scraper
│   ├── evaluation/
│   │   └── protocol.py      # French evaluation protocol
│   └── models/
│       └── listing.py       # Pydantic data models
├── requirements.txt
└── README.md
```

## Troubleshooting

### SeLoger returns 403 Forbidden

SeLoger has aggressive anti-bot protection. Try:

1. Use cached pages if available (script auto-caches fetched pages)
2. Use headless mode: `--mode headless`
3. Wait and retry later (rate limiting)

### PAP returns 403 Forbidden

The scraper uses `cloudscraper` which should handle most cases. If blocked:

1. Clear cookies and retry
2. Use headless mode: `--mode headless`

### Brotli decoding error

This was fixed by using `cloudscraper` instead of raw `httpx`. Update your dependencies:

```bash
pip install --upgrade cloudscraper requests
```

## License

MIT
