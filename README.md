# 🏠 French Real Estate Analyzer

A comprehensive tool for scraping, evaluating, and comparing French real estate listings from SeLoger and PAP.fr.

## Features

- **Web Scraping**: Extract listing data from SeLoger.com and PAP.fr
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

## Quick Start

### Compare Multiple Listings

```bash
python scripts/compare_listings.py \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/259946399.htm" \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/253220767.htm" \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/256211255.htm" \
  "https://www.seloger.com/annonces/achat/appartement/montrouge-92/260105567.htm" \
  -m requests --detailed
```

### Analyze a Single Listing

```bash
# Basic extraction
python scripts/test_scraper.py "https://www.seloger.com/annonces/achat/appartement/..." -m requests

# With full evaluation report
python scripts/test_scraper.py "https://www.seloger.com/annonces/achat/appartement/..." -m requests --evaluate
```

## Evaluation Criteria

The French Real Estate Evaluation Protocol scores listings based on 5 key criteria (in order of importance):

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
# Compare multiple listings
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
  -m, --mode      Fetch mode: requests, simple, headless
  -e, --evaluate  Run full evaluation and show report
  -v, --verbose   Show description and raw JSON
  -c, --cached    Use cached HTML only
  -r, --refresh   Clear cache and refetch
```

## Output Example

```
📋 LISTING COMPARISON SUMMARY
====================================================================================================
#   City            Surface    Price        €/m²       Score    Rating   Risk         DPE   Value   
----------------------------------------------------------------------------------------------------
→1  Montrouge       56         550,000      9,821      86       ★★★★☆    🟢 Low        B     15.5    
 2  Montrouge       61         550,000      9,016      84       ★★★★☆    🟢 Low        C     15.3    
 3  Montrouge       62         580,000      9,355      79       ★★★★☆    🟢 Low        D     13.7    
 4  Montrouge       60         530,000      8,833      79       ★★★★☆    🟠 High       E     14.9    
----------------------------------------------------------------------------------------------------

💡 RECOMMENDATION
====================================================================================================
  🏆 BEST OVERALL SCORE: #1 Montrouge (Score: 86/100)
  💰 BEST VALUE: #1 Montrouge (15.5 pts per 100k€)
  💵 LOWEST PRICE: #4 Montrouge (530,000€)
  🛡️ LOWEST RISK: #1 Montrouge (🟢 Low Risk)
```

## Data Extracted

### From Structured Data
- Price, Surface, Rooms, Bedrooms
- DPE/GES Energy Rating
- City, Postal Code
- Floor, Elevator

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

```
real_estate_analyzer/
├── scripts/
│   ├── test_scraper.py      # Single listing analysis
│   └── compare_listings.py  # Multi-listing comparison
├── src/
│   ├── scraper/
│   │   ├── base.py          # Core scraping infrastructure
│   │   ├── seloger.py       # SeLoger.com scraper
│   │   └── pap.py           # PAP.fr scraper
│   ├── evaluation/
│   │   └── protocol.py      # French evaluation protocol
│   └── models/
│       └── listing.py       # Pydantic data models
└── requirements.txt
```

## License

MIT


CURRENT FAILURES

 Extraction failed: Request error fetching https://www.seloger.com/annonces/achat/appartement/montrouge-92/259946399.htm: ('Received response with content-encoding: br, but failed to decode it.', error("brotli: decoder process called with data when 'can_accept_more_data()' is False"))
