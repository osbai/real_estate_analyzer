# Real Estate Listing Analyzer - Implementation Plan

## Overview
A Python application that analyzes real estate listings from URLs, compares them to market data, evaluates profitability, and generates comprehensive reports for potential buyers/investors.

---

## Phase 1: Project Setup & Core Structure

### 1.1 Initialize Project
- Create project directory structure:
  ```
  real_estate_analyzer/
  ├── src/
  │   ├── __init__.py
  │   ├── main.py              # Entry point / CLI
  │   ├── config.py            # Configuration settings
  │   ├── scraper/
  │   │   ├── __init__.py
  │   │   ├── base.py          # Abstract scraper interface
  │   │   ├── zillow.py        # Zillow scraper
  │   │   ├── redfin.py        # Redfin scraper
  │   │   └── manual.py        # Manual data input fallback
  │   ├── analyzer/
  │   │   ├── __init__.py
  │   │   ├── market.py        # Market comparison logic
  │   │   ├── scoring.py       # Property scoring system
  │   │   └── comparables.py   # Find comparable listings
  │   ├── financial/
  │   │   ├── __init__.py
  │   │   ├── mortgage.py      # Mortgage calculations
  │   │   ├── roi.py           # ROI & cash flow analysis
  │   │   └── projections.py   # Future value projections
  │   ├── report/
  │   │   ├── __init__.py
  │   │   ├── generator.py     # Report generation
  │   │   ├── templates/       # Report templates
  │   │   └── questions.py     # Seller question generator
  │   └── models/
  │       ├── __init__.py
  │       └── listing.py       # Data models (Pydantic)
  ├── tests/
  ├── requirements.txt
  ├── pyproject.toml
  └── README.md
  ```

### 1.2 Dependencies
- `requests` / `httpx` - HTTP requests
- `beautifulsoup4` / `selectolax` - HTML parsing
- `pydantic` - Data validation and models
- `rich` - Beautiful CLI output
- `jinja2` - Report templating
- `typer` - CLI framework
- `weasyprint` (optional) - PDF generation

---

## Phase 2: Data Models & Scraping

### 2.1 Define Data Models
Create Pydantic models for:
- `Listing` - Core listing data (price, address, sqft, bedrooms, bathrooms, year built, lot size, etc.)
- `PropertyFeatures` - Amenities, condition, upgrades
- `LocationData` - Neighborhood stats, nearby amenities, schools
- `FinancialParams` - User inputs (interest rate, down payment, holding period)

### 2.2 Implement Scraper Interface
- Create abstract `BaseScraper` class with method: `extract(url) -> Listing`
- Implement platform-specific scrapers:
  - **Zillow**: Parse Zillow listing pages
  - **Redfin**: Parse Redfin listing pages
  - **Manual Input**: Allow user to manually input data when scraping fails
- Add URL detection to auto-select appropriate scraper

### 2.3 Handle Scraping Challenges
- Implement retry logic with exponential backoff
- Add user-agent rotation
- Cache scraped data to avoid repeated requests
- Graceful fallback to manual input when blocked

---

## Phase 3: Market Analysis Engine

### 3.1 Comparable Properties Finder
- Extract location/neighborhood from listing
- Scrape or fetch similar listings in the area (same bedrooms, similar sqft)
- Filter by relevant criteria (sold within last 6 months, similar age)

### 3.2 Market Comparison Metrics
- **Price per Square Foot** vs. neighborhood average
- **Days on Market** comparison
- **Price History** - has it been reduced?
- **Neighborhood Trends** - appreciating or depreciating area?
- **Listing vs. Sold Price Ratio** for comparable properties

### 3.3 Scoring System
Create weighted scoring for:
- **Value Score** (0-100): Price competitiveness
- **Location Score** (0-100): Neighborhood quality, amenities
- **Condition Score** (0-100): Age, updates, maintenance needs
- **Investment Score** (0-100): Rental potential, appreciation outlook

---

## Phase 4: Financial Analysis Module

### 4.1 Mortgage Calculator
- Monthly payment calculation (P&I, taxes, insurance, PMI)
- Amortization schedule generation
- Compare different scenarios (15yr vs 30yr, varying down payments)

### 4.2 Investment Analysis
- **Cash Flow Analysis**: Rental income potential vs. expenses
- **Cap Rate**: Net operating income / purchase price
- **Cash-on-Cash Return**: Annual cash flow / total cash invested
- **ROI Projection**: 5, 10, 20-year projections with appreciation estimates

### 4.3 Break-Even Analysis
- Calculate how long to recoup investment
- Compare buy vs. rent scenarios

---

## Phase 5: Report Generation

### 5.1 Report Structure
1. **Executive Summary**: Quick verdict with key metrics
2. **Property Overview**: Extracted listing details
3. **Market Analysis**: Comparison with similar properties
4. **Financial Breakdown**:
   - Monthly costs
   - Investment returns
   - Profitability projections
5. **Strengths**: What makes this property attractive
6. **Concerns**: Red flags and areas needing attention
7. **Questions for Seller**: Auto-generated list of important questions

### 5.2 Output Formats
- **Terminal**: Rich formatted CLI output
- **Markdown**: Portable text report
- **HTML**: Styled web report
- **PDF**: Professional document (optional)

### 5.3 Question Generator
Auto-generate questions based on:
- Property age (maintenance history, major repairs)
- HOA presence (fees, restrictions, reserves)
- Pricing (room for negotiation, multiple offers)
- Disclosures (known issues, past problems)
- Rental potential (current tenants, rental history)

---

## Phase 6: CLI Interface

### 6.1 Commands
```bash
# Analyze a single listing
python -m real_estate_analyzer analyze <url> --rate 6.5 --down-payment 20

# Compare multiple listings
python -m real_estate_analyzer compare <url1> <url2> <url3>

# Generate full report
python -m real_estate_analyzer report <url> --output report.pdf

# Interactive mode (guided input)
python -m real_estate_analyzer interactive
```

### 6.2 Configuration Options
- Default interest rate
- Default down payment percentage
- Preferred report format
- API keys for data services (if used)

---

## Phase 7: Testing & Documentation

### 7.1 Testing
- Unit tests for financial calculations
- Integration tests for scrapers (with mocked responses)
- Sample listings for end-to-end testing

### 7.2 Documentation
- README with setup instructions
- Usage examples
- API documentation for programmatic use

---

## Technical Considerations

### Data Sources
- **Primary**: Web scraping (with ToS considerations)
- **Alternative**: RapidAPI real estate APIs, Zillow API (deprecated but alternatives exist)
- **Fallback**: Manual data entry via CLI prompts

### Error Handling
- Graceful degradation when data unavailable
- Clear user feedback on what's missing
- Partial reports when some data cannot be fetched

### Extensibility
- Plugin architecture for new scrapers
- Configurable scoring weights
- Custom report templates

---

## Estimated Implementation Order
1. Phase 1: Project Setup (foundation)
2. Phase 2: Data Models & Scraping (core functionality)
3. Phase 4: Financial Analysis (high user value)
4. Phase 5: Report Generation (user-facing output)
5. Phase 3: Market Analysis (enhanced features)
6. Phase 6: CLI Interface (polish)
7. Phase 7: Testing & Documentation (production-ready)
