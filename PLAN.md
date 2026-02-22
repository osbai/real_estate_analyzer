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

---

# 🇫🇷 FRANCE-SPECIFIC ADVANCED FEATURES

## Phase 8: Investment Logic Layer

### 8.1 Yield Calculator
Automatically calculate key financial metrics for investment properties.

**Gross Yield:**
```
Yield_Gross = (Monthly Rent × 12) / Purchase Price
```

**Net Yield (Rendement Net):**
```
Yield_Net = [(Monthly Rent × 12) - Charges - Taxes] / [Purchase Price + Notary Fees]
```

**Implementation:**
- Add `market_rent` field to Listing model (scraped or user-input)
- Create `src/financial/yield_calculator.py`:
  - `calculate_gross_yield(price, monthly_rent)`
  - `calculate_net_yield(price, monthly_rent, charges, taxes, notary_fees)`
- Display yield comparison vs. market average (~3-5% in major cities, ~6-8% in smaller towns)

### 8.2 Notary Fees Auto-Calculator (Frais de Notaire)
French notary fees are a hidden but significant cost.

| Property Type | Notary Fee Rate |
|---------------|-----------------|
| **Ancien** (old build, >5 years) | ~7-8% of purchase price |
| **VEFA/Neuf** (new build, <5 years) | ~2-3% of purchase price |

**Implementation:**
- Detect property type from listing (look for "VEFA", "neuf", "livraison" keywords)
- Auto-calculate and display:
  - **Total Acquisition Cost** = Purchase Price + Frais de Notaire
  - Flag if listing description mentions reduced fees ("frais de notaire réduits")

### 8.3 Cash Flow Modeler
Interactive loan simulation to assess "effort d'épargne" (monthly out-of-pocket).

**Parameters to Toggle:**
| Parameter | Options |
|-----------|---------|
| Loan Duration | 15 / 20 / 25 years |
| Interest Rate | User input (default: current market ~3.5-4%) |
| Down Payment | 10% / 20% / 30% |
| Insurance Rate | ~0.3% annually |

**Output:**
- Monthly mortgage payment (mensualité)
- Monthly rental income (if investment)
- **Cash Flow** = Rent - Mortgage - Charges - Taxes
- Status: 🟢 **Cash Flow Positive** or 🔴 **Effort d'épargne: €XXX/month**

**Implementation:**
- Create `src/financial/cashflow.py`:
  - `calculate_monthly_payment(principal, rate, years)`
  - `simulate_cashflow(listing, rent, loan_params)`
- Add CLI flag: `--cashflow --rate 3.5 --duration 25`

---

## Phase 9: Market Benchmarking (Comps)

### 9.1 DVF Integration (Demande de Valeur Foncière)
Integrate French government's open data on actual sale prices.

**Data Source:** https://app.dvf.etalab.gouv.fr/ (API available)

**Features:**
- Fetch sales history for the same building/street in last 5 years
- Show price evolution: "Apt in this building sold for €8,200/m² in 2022"
- Compare listing's €/m² to neighborhood median

**Implementation:**
- Create `src/analyzer/dvf.py`:
  - `fetch_sales_history(postal_code, street, years=5)`
  - `get_neighborhood_median_price(postal_code, property_type)`
- Display in report:
  ```
  📊 MARKET CONTEXT (DVF Data)
  ─────────────────────────────
  Neighborhood median: €9,100/m²
  This listing: €8,700/m² → 🟢 4.4% below market

  Recent sales in building:
  • 2023-06: 48m² sold for €420,000 (€8,750/m²)
  • 2022-02: 52m² sold for €445,000 (€8,558/m²)
  ```

### 9.2 "Motivated Seller" Tracker (Price History)
Track listings over time to detect price drops.

**Implementation:**
- Store listing snapshots in local SQLite database
- On each scrape, compare with previous snapshot
- Flag and display:
  ```
  ⚡ PRICE ALERT: Reduced from €500,000 → €475,000 (-5%)
  Days on market: 87 days
  🏷️ Motivated Seller Signal
  ```

- Create `src/tracker/price_history.py`:
  - `record_snapshot(listing_id, price, timestamp)`
  - `get_price_changes(listing_id)`
  - `detect_motivated_seller(changes, threshold=0.05)`

---

## Phase 10: Legal & Risk Screener

### 10.1 DPE (Energy Performance) Analysis
Critical for French rentals due to upcoming bans.

**Rental Ban Schedule:**
| DPE Rating | Status |
|------------|--------|
| G | ❌ **Banned since January 2025** |
| F | ⚠️ **Banned from 2028** |
| E | ⚠️ **Banned from 2034** |
| A-D | ✅ No restrictions |

**Implementation:**
- Already partially implemented in `protocol.py`
- Add enhanced warnings:
  ```
  ⚠️ DPE ALERT: Rating F
  ────────────────────────
  Status: Rental ban effective January 2028
  Remaining rental window: ~3 years
  Recommendation: Budget for energy renovation

  💡 RENOVATION ESTIMATE
  Current: F (>330 kWh/m²/year)
  Target: D (<250 kWh/m²/year)
  Estimated cost: €25,000 - €50,000 (€500-€1000/m²)

  Typical works required:
  • Window replacement (double/triple glazing)
  • Insulation (walls, roof, floors)
  • Heating system upgrade (heat pump)
  • Ventilation (VMC double flux)
  ```

### 10.2 Renovation Cost Estimator
Provide rough estimates for DPE improvement works.

| DPE Upgrade | Typical Cost |
|-------------|--------------|
| G → D | €800 - €1,200/m² |
| F → D | €500 - €1,000/m² |
| E → D | €300 - €600/m² |

**Implementation:**
- Create `src/analyzer/renovation.py`:
  - `estimate_renovation_cost(current_dpe, target_dpe, surface)`
  - Factor in property type (apartment vs house)
  - Include French subsidies info (MaPrimeRénov', CEE)

### 10.3 Urbanism Risk Checker
Flag regulatory risks specific to French real estate.

**Zone Tendue (Rent Control Areas):**
- Check if property is in a "zone tendue" (rent-controlled city)
- List: Paris, Lyon, Marseille, Bordeaux, Lille, Montpellier, etc.
- Impact: Rent increases capped, encadrement des loyers applies

**Major Projects Nearby:**
- Flag proximity to:
  - Grand Paris Express stations (opportunity: +15-25% value)
  - Future tramway/metro lines
  - ZAC (Zone d'Aménagement Concerté) developments

**Implementation:**
- Create `src/analyzer/urbanism.py`:
  - `is_zone_tendue(postal_code)` - reference INSEE list
  - `check_nearby_projects(lat, lon)` - scrape Grand Paris Express data
- Display:
  ```
  🏛️ URBANISM CHECK
  ─────────────────
  Zone Tendue: ✅ Yes (Montrouge, 92120)
  → Encadrement des loyers applies
  → Rent cap: €24.50/m² (reference) + 20% max

  📍 Nearby Projects:
  • Grand Paris Express - Line 15 (Châtillon-Montrouge)
    Status: Under construction, opening 2025
    Distance: 450m
    Impact: 🟢 Positive (+15-20% property value expected)
  ```

---

## Phase 11: Advanced User Features

### 11.1 "Dossier de Location" Auto-Sender
For renters, speed is critical. Pre-upload documents and auto-apply.

**User Uploads:**
- Pièce d'identité (ID)
- 3 derniers bulletins de salaire (paystubs)
- Avis d'imposition (tax notice)
- Attestation employeur (employment certificate)
- Quittances de loyer (rent receipts)

**Implementation:**
- Create `src/dossier/manager.py`:
  - Store encrypted documents locally
  - `compile_dossier(user_profile)` → generates PDF package
  - `send_dossier(agent_email, listing_url)` → auto-email

- Alert System:
  - Define search criteria (location, price range, surface)
  - Monitor listing sites for new matches
  - Auto-send dossier within minutes of listing appearing

### 11.2 Agentic Inquiry Drafting (LLM-Powered)
Use Claude to generate personalized, professional inquiries in French.

**Example Output:**
```
Objet: Demande de visite - Appartement 3P, 50m², Montrouge

Madame, Monsieur,

Je me permets de vous contacter suite à votre annonce pour
l'appartement situé au 3ème étage avec ascenseur à Montrouge.

J'ai particulièrement noté la présence d'une terrasse de 16m²
ainsi que le classement DPE A, ce qui correspond parfaitement
à mes critères de recherche.

Mon profil: CDI depuis 4 ans, revenus 3x le loyer demandé.
Je dispose d'un dossier complet et suis disponible pour une
visite dès cette semaine.

Cordialement,
[User Name]
[Phone]
```

**Implementation:**
- Create `src/outreach/inquiry_generator.py`:
  - Extract key listing features (terrace, DPE, floor, amenities)
  - Generate personalized message via Claude API
  - Include user's strong points (salary, stability, references)
  - Offer to attach complete dossier

- CLI command:
  ```bash
  python -m real_estate_analyzer inquire <url> --profile user.json
  ```

---

## Data Sources Summary

| Data | Source | Type |
|------|--------|------|
| Listing details | PAP.fr, SeLoger.com | Scraping |
| Historical prices | DVF (etalab.gouv.fr) | API/Open Data |
| Zone Tendue list | INSEE, legifrance.gouv.fr | Static reference |
| Grand Paris Express | societedugrandparis.fr | Scraping/API |
| DPE regulations | ADEME, legifrance.gouv.fr | Static reference |
| Current mortgage rates | meilleurtaux.com, pretto.fr | Scraping |

---

## Updated Implementation Priority

| Priority | Phase | Description | Value |
|----------|-------|-------------|-------|
| 🔴 High | 8.1-8.3 | Yield & Cash Flow Calculator | Core investor decision tool |
| 🔴 High | 10.1 | DPE Analysis & Warnings | Legal compliance, risk avoidance |
| 🟡 Medium | 9.1 | DVF Integration | Market context, negotiation power |
| 🟡 Medium | 8.2 | Notary Fees Calculator | True cost visibility |
| 🟡 Medium | 10.2 | Renovation Estimator | Budget planning |
| 🟢 Lower | 9.2 | Price Tracker | Opportunity detection |
| 🟢 Lower | 10.3 | Urbanism Checker | Long-term value assessment |
| 🟢 Lower | 11.1-11.2 | Dossier & Outreach | Competitive advantage |

---

## Next Steps

1. **Immediate**: Implement yield calculator and notary fee logic
2. **Short-term**: Integrate DVF API for market benchmarking
3. **Medium-term**: Build DPE risk screener with renovation estimates
4. **Long-term**: Add tracking database and agentic features
