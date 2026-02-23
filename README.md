# 🏠 French Real Estate Analyzer

A comprehensive tool for scraping, evaluating, and comparing French real estate listings from SeLoger, PAP.fr, and LeBonCoin.

## Features

- **Multi-Source Scraping**: Extract listing data from SeLoger.com, PAP.fr, and LeBonCoin in the same command
- **Anti-Bot Bypass**: Uses `cloudscraper` and session-based requests to bypass Cloudflare and DataDome protections
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

### 1. Search for Listings on SeLoger

Find listings matching your criteria directly from SeLoger search results:

```bash
# Copy a SeLoger search URL to your clipboard, then run:
python scripts/search_seloger.py --all-pages

# Results are cached automatically
# Example output:
# ✅ Saved 64 listings to: .cache/searches/seloger_search_20260222_213842_0dda2d10.json
```

### 2. Generate Investment Report

Analyze and export all listings with investment metrics:

```bash
# Generate investment report (sorted by cash flow, filtered by quality)
python scripts/compare_listings.py \
  --from-cache "seloger_search_20260222_213842_0dda2d10.json" \
  --investment \
  --export investment_report.csv \
  --interest-rate 3.1
```

The CSV includes: Price, Total Cost, Rent, Gross Yield, Net Yield, Cash Flow, Score, DPE, and URL for each listing.

### Automatic Filters

By default, listings are automatically filtered to show only quality investments:

| Filter | Description | Override |
|--------|-------------|----------|
| 🚩 Red flags | Excludes DPE G/F, long commutes, etc. | `--include-all` |
| 🗺️ Île-de-France only | Excludes listings outside IDF | - |
| ❓ Unknown cities | Excludes listings with no city | - |
| 🚇 Commute time | Filter by max commute to Paris | `--max-commute 30` |

### Sorting

| Mode | Default Sort | Description |
|------|--------------|-------------|
| Standard | Score | Best quality first |
| `--investment` | **Cash Flow** | Highest positive cash flow first |
| `--sort yield` | Gross Yield | Highest yield first |
| `--sort value` | Value Score | Best bang for buck first |

### Additional Options

```bash
# Filter by max commute time to Paris (in minutes)
python scripts/compare_listings.py --from-cache "search.json" --investment --max-commute 30

# Include listings with red flags (DPE issues, long commute, etc.)
python scripts/compare_listings.py --from-cache "search.json" --include-all

# Limit number of listings to analyze
python scripts/compare_listings.py --from-cache "search.json" --limit 10

# Sort by different criteria
python scripts/compare_listings.py --from-cache "search.json" --sort yield
python scripts/compare_listings.py --from-cache "search.json" --sort value
python scripts/compare_listings.py --from-cache "search.json" --sort price
```

### Red Flags (Automatic Detection)

The following issues are detected and flagged:

| Red Flag | Description |
|----------|-------------|
| DPE G | Cannot be legally rented (banned since 2025) |
| DPE F | Rental ban coming in 2028 |
| Long commute | > 35 minutes to Paris |
| Remote location | Poor transport connectivity |
| Ground floor (RDC) | Security/noise concerns |
| Ongoing procedures | Legal issues in building |

### Compare Listings from Multiple Sources

You can compare listings from both PAP and SeLoger in the same command:

```bash
# Compare PAP and SeLoger listings side-by-side (with fresh fetch, no cache)
python scripts/compare_listings.py \
  "https://www.pap.fr/annonces/appartement-montrouge-92120-r461901225" \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/253220767.htm" \
  --detailed --no-cache

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
| `requests` | requests | Plain HTTP requests | **SeLoger** (default) |
| `cloudscraper` | cloudscraper | Bypasses Cloudflare/anti-bot | **PAP** (default) |
| `simple` | httpx | Async-capable HTTP client | Testing |
| `headless` | Playwright | Full browser rendering | JS-heavy pages, captchas |

### Supported Sites

| Site | Default Mode | Status | Notes |
|------|--------------|--------|-------|
| **PAP.fr** | `cloudscraper` | ✅ Working | Bypasses Cloudflare protection |
| **SeLoger.com** | `requests` | ✅ Working | Plain requests with session cookies |
| **LeBonCoin.fr** | `requests` | ✅ Working | Session-based requests bypass DataDome |

### Testing LeBonCoin Scraper

LeBonCoin uses DataDome anti-bot protection. The scraper bypasses it by:
1. Using a session to maintain cookies
2. Visiting the homepage first to get initial cookies
3. Using full browser-like headers including `sec-ch-ua`

```bash
# Test a LeBonCoin listing
python scripts/test_scraper.py "https://www.leboncoin.fr/ad/ventes_immobilieres/3135532890" --evaluate

# Compare listings from multiple sources
python scripts/compare_listings.py \
  "https://www.leboncoin.fr/ad/ventes_immobilieres/3135532890" \
  "https://www.seloger.com/annonces/achat/appartement/drancy-93/123456789.htm" \
  --investment

# LeBonCoin extracts these fields:
# - Title, price, surface area
# - City, postal code
# - DPE/GES energy ratings
# - Rooms, bedrooms, floor
# - Amenities (elevator, balcony, cellar, parking)
# - Agent info (pro vs private seller)
# - Annual charges
```

### Searching LeBonCoin

Due to strict anti-bot protection on search pages, the recommended workflow is to manually save search results from your browser:

**Step 1: Save search HTML from browser**
```bash
# 1. Open LeBonCoin search in your browser with your filters - for example:
# https://www.leboncoin.fr/recherche?category=9&locations=Aubervilliers_93300__48.9136_2.38237_2133_5000&price=min-300000&rooms=2-2&square=38-max&bedrooms=1-1&real_estate_type=2&immo_sell_type=old%2Cnew&floor_property=upper_floor&energy_rate=a%2Cb%2Cc%2Cd&global_condition=1%2C2%2C3&page=3
# 2. Right-click → "View Page Source" (or Cmd+U / Ctrl+U)
# 3. Save the HTML to a file (e.g., leboncoin_page1.html)
# 4. If multiple pages, repeat for each page
```

**Step 2: Extract listing URLs**
```bash
# Extract from a single file (replace "search.html" with your filename)
grep -oh '"list_id":[0-9]*' search.html | sort -u | \
  sed 's/"list_id":/https:\/\/www.leboncoin.fr\/ad\/ventes_immobilieres\//' > urls.txt

# Extract from multiple files
grep -oh '"list_id":[0-9]*' file1.html file2.html file3.html | sort -u | \
  sed 's/"list_id":/https:\/\/www.leboncoin.fr\/ad\/ventes_immobilieres\//' > urls.txt
```

**Step 3: Analyze listings**
```bash
# Compare all listings with investment analysis
cat urls.txt | xargs python scripts/compare_listings.py --investment

# Export to CSV
cat urls.txt | xargs python scripts/compare_listings.py --investment --export investment_report.csv --interest-rate 3.1

# Compare first 10 listings only
python scripts/compare_listings.py $(cat urls.txt | head -10 | tr '\n' ' ') --investment
```

**Alternative: Analyze individual listings directly**
```bash
# Single listings work reliably without rate limiting
python scripts/test_scraper.py "https://www.leboncoin.fr/ad/ventes_immobilieres/3149772131" --evaluate
```

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
  -m, --mode      Fetch mode: requests, cloudscraper, simple, headless
                  (default: auto-detect per site - PAP→cloudscraper, SeLoger→requests)
  -s, --sort      Sort by: score, price, price_m2, surface, value (default: score)
  -d, --detailed  Show detailed side-by-side comparison
  -e, --export    Export to CSV file
  --no-cache      Disable cache, always fetch fresh data from network
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
│   ├── compare_listings.py  # Multi-listing comparison
│   └── search_seloger.py    # Search SeLoger and extract listing URLs
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
