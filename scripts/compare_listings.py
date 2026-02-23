#!/usr/bin/env python3
"""Compare and rank French real estate listings.

This script helps you:
1. Compare multiple listings side-by-side
2. Rank them by overall score and value metrics
3. Identify the "best" options based on your criteria
4. Analyze investment potential (yield, cash flow, notary fees)

Usage:
    # Compare two listings
    python scripts/compare_listings.py URL1 URL2

    # Compare multiple listings
    python scripts/compare_listings.py URL1 URL2 URL3 URL4

    # Compare listings from a cached search
    python scripts/compare_listings.py --from-cache seloger_search_20240101_120000_abc123.json
    python scripts/compare_listings.py --from-cache seloger_search.json --limit 5

    # Rank by specific criteria
    python scripts/compare_listings.py URL1 URL2 --sort price
    python scripts/compare_listings.py URL1 URL2 --sort score
    python scripts/compare_listings.py URL1 URL2 --sort value
    python scripts/compare_listings.py URL1 URL2 --sort yield

    # Show detailed comparison
    python scripts/compare_listings.py URL1 URL2 --detailed

    # Show investment analysis
    python scripts/compare_listings.py URL1 URL2 --investment
    python scripts/compare_listings.py URL1 URL2 --investment --rent 1200

    # Export to CSV for spreadsheet analysis
    python scripts/compare_listings.py URL1 URL2 --export comparison.csv
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Cache directory for search results (same as search_seloger.py)
SEARCH_CACHE_DIR = Path(__file__).parent.parent / ".cache" / "searches"

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import EvaluationResult, FrenchRealEstateEvaluator
from src.financial import InvestmentAnalyzer, InvestmentReport
from src.models.listing import Listing
from src.scraper import FetchMode, get_scraper


@dataclass
class ListingAnalysis:
    """Combined listing data and evaluation."""

    listing: Listing
    evaluation: EvaluationResult
    rank: int = 0
    investment: Optional[InvestmentReport] = None

    @property
    def value_score(self) -> float:
        """Calculate value score (quality per euro)."""
        return (self.evaluation.overall_score / self.listing.price_info.price) * 100000

    @property
    def price_per_point(self) -> float:
        """Price per evaluation point (lower is better value)."""
        if self.evaluation.overall_score == 0:
            return float("inf")
        return self.listing.price_info.price / self.evaluation.overall_score

    @property
    def gross_yield(self) -> Optional[float]:
        """Gross yield if investment analysis available."""
        return self.investment.gross_yield if self.investment else None

    @property
    def net_yield(self) -> Optional[float]:
        """Net yield if investment analysis available."""
        return self.investment.net_yield if self.investment else None

    @property
    def monthly_cash_flow(self) -> Optional[float]:
        """Monthly cash flow if investment analysis available."""
        return self.investment.monthly_cash_flow if self.investment else None


def fetch_listing(
    url: str, mode: Optional[str] = None, use_cache: bool = True
) -> Optional[Listing]:
    """Fetch and parse a listing from URL.

    If mode is None, the scraper will use its default mode (PAP→cloudscraper, SeLoger→requests).
    """
    fetch_mode = None
    if mode:
        fetch_mode = {
            "requests": FetchMode.REQUESTS,
            "cloudscraper": FetchMode.CLOUDSCRAPER,
            "simple": FetchMode.SIMPLE,
            "headless": FetchMode.HEADLESS,
        }.get(mode)

    try:
        # If no mode specified, scraper uses its default
        if fetch_mode:
            scraper = get_scraper(url, mode=fetch_mode)
        else:
            scraper = get_scraper(url)
        listing = scraper.extract(url, use_cache=use_cache)
        scraper.close()
        return listing
    except Exception as e:
        print(f"  ✗ Error fetching: {e}")
        return None


def analyze_listings(
    urls: list[str], mode: Optional[str] = None, use_cache: bool = True
) -> list[ListingAnalysis]:
    """Fetch, parse and evaluate multiple listings.

    If mode is None, each scraper uses its default mode (PAP→cloudscraper, SeLoger→requests).
    """
    evaluator = FrenchRealEstateEvaluator()
    analyses = []

    print("\n📊 Fetching and analyzing listings...\n")

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url[:60]}...")
        listing = fetch_listing(url, mode, use_cache)
        if listing:
            evaluation = evaluator.evaluate(listing)
            analyses.append(ListingAnalysis(listing=listing, evaluation=evaluation))
            print(
                f"        ✓ {listing.address.city} - {listing.surface_area}m² - {listing.price_info.price:,}€"
            )
        else:
            print(f"        ✗ Failed to fetch")

    return analyses


def print_summary_table(
    analyses: list[ListingAnalysis], sort_by: str = "score", skip_sort: bool = False
):
    """Print a compact summary table of all listings."""
    if not analyses:
        print("\n⚠️ No listings to compare.")
        return

    # Sort analyses (unless already sorted externally)
    if not skip_sort:
        if sort_by == "price":
            analyses.sort(key=lambda x: x.listing.price_info.price)
        elif sort_by == "price_m2":
            analyses.sort(key=lambda x: x.listing.price_per_sqm)
        elif sort_by == "surface":
            analyses.sort(key=lambda x: x.listing.surface_area, reverse=True)
        elif sort_by == "value":
            analyses.sort(key=lambda x: x.value_score, reverse=True)
        else:  # score (default)
            analyses.sort(key=lambda x: x.evaluation.overall_score, reverse=True)

        # Assign ranks
        for i, analysis in enumerate(analyses, 1):
            analysis.rank = i

    # Column widths
    city_w = 18

    print("\n" + "=" * 105)
    print("📋 LISTING COMPARISON SUMMARY")
    print("=" * 105)

    # Header
    print(
        f"{'#':<3} {'City':<{city_w}} {'Surface':<8} {'Price':<12} {'€/m²':<8} "
        f"{'Score':<6} {'Rating':<8} {'Risk':<8} {'DPE':<4} {'Value':<6}"
    )
    print("-" * 105)

    # Rows
    for a in analyses:
        l = a.listing
        e = a.evaluation

        # Truncate long city names
        city = l.address.city or "Unknown"
        if len(city) > city_w - 1:
            city = city[: city_w - 2] + "…"

        # Highlight best in category
        is_best_score = a.rank == 1 and sort_by == "score"
        is_best_value = a.rank == 1 and sort_by == "value"
        prefix = "→" if is_best_score or is_best_value else " "

        risk_short = {
            "🟢 Low Risk": "🟢 Low",
            "🟡 Medium Risk": "🟡 Med",
            "🟠 High Risk": "🟠 High",
            "🔴 Critical Risk": "🔴 Crit",
        }.get(e.risk_level.value, e.risk_level.value[:8])

        print(
            f"{prefix}{a.rank:<2} {city:<{city_w}} {l.surface_area:<8.0f} "
            f"{l.price_info.price:<12,} {l.price_per_sqm:<8,.0f} "
            f"{e.overall_score:<6.0f} {e.rating.value:<8} {risk_short:<8} "
            f"{l.energy_rating.energy_class.value:<4} {a.value_score:<6.1f}"
        )

    print("-" * 105)
    print(
        f"Sorted by: {sort_by.upper()} | Value = Score per 100k€ (higher = better deal)"
    )


def print_detailed_comparison(analyses: list[ListingAnalysis]):
    """Print detailed side-by-side comparison."""
    if len(analyses) < 2:
        print("\n⚠️ Need at least 2 listings for detailed comparison.")
        return

    print("\n" + "=" * 100)
    print("🔍 DETAILED COMPARISON")
    print("=" * 100)

    # Compare key metrics
    metrics = [
        ("IDENTIFICATION", None),
        ("City", lambda a: a.listing.address.city),
        ("Postal Code", lambda a: a.listing.address.postal_code),
        ("Street", lambda a: a.listing.address.street or "N/A"),
        ("", None),
        ("PRICE & SURFACE", None),
        ("Price", lambda a: f"{a.listing.price_info.price:,}€"),
        ("Surface", lambda a: f"{a.listing.surface_area}m²"),
        ("Price/m²", lambda a: f"{a.listing.price_per_sqm:,.0f}€"),
        (
            "Annual Charges",
            lambda a: (
                f"{a.listing.price_info.annual_charges:,}€/yr"
                if a.listing.price_info.annual_charges
                else "N/A"
            ),
        ),
        ("", None),
        ("EVALUATION SCORES", None),
        ("Overall Score", lambda a: f"{a.evaluation.overall_score:.0f}/100"),
        ("Rating", lambda a: a.evaluation.rating.value),
        ("Risk Level", lambda a: a.evaluation.risk_level.value),
        ("Value Score", lambda a: f"{a.value_score:.1f}"),
        (
            "Fair Value Est.",
            lambda a: (
                f"{a.evaluation.fair_value_estimate:,.0f}€"
                if a.evaluation.fair_value_estimate
                else "N/A"
            ),
        ),
        (
            "Negotiation",
            lambda a: (
                f"-{a.evaluation.negotiation_margin:.0f}%"
                if a.evaluation.negotiation_margin
                else "None"
            ),
        ),
        ("", None),
        ("ENERGY & BUILDING", None),
        ("DPE", lambda a: a.listing.energy_rating.energy_class.value),
        ("GES", lambda a: a.listing.energy_rating.ges_class.value),
        ("Building Era", lambda a: a.listing.features.building_era or "N/A"),
        (
            "Copro Lots",
            lambda a: (
                str(a.listing.building.total_lots)
                if a.listing.building.total_lots
                else "N/A"
            ),
        ),
        (
            "Procedures",
            lambda a: (
                "Yes ⚠️"
                if a.listing.building.has_ongoing_procedures
                else (
                    "No ✓"
                    if a.listing.building.has_ongoing_procedures is not None
                    else "N/A"
                )
            ),
        ),
        ("", None),
        ("FEATURES", None),
        (
            "Rooms",
            lambda a: (
                str(a.listing.features.rooms) if a.listing.features.rooms else "N/A"
            ),
        ),
        (
            "Bedrooms",
            lambda a: (
                str(a.listing.features.bedrooms)
                if a.listing.features.bedrooms
                else "N/A"
            ),
        ),
        (
            "Floor",
            lambda a: (
                str(a.listing.features.floor)
                if a.listing.features.floor is not None
                else "N/A"
            ),
        ),
        ("Elevator", lambda a: "✓" if a.listing.features.has_elevator else "✗"),
        ("Condition", lambda a: a.listing.features.condition or "N/A"),
        ("Exposure", lambda a: a.listing.features.exposure or "N/A"),
        ("", None),
        ("TRANSPORT", None),
        (
            "Metro",
            lambda a: (
                ", ".join(a.listing.transport.metro_lines)
                if a.listing.transport.metro_lines
                else "N/A"
            ),
        ),
        ("Distance", lambda a: a.listing.transport.distance_to_transport or "N/A"),
        ("", None),
        ("AMENITIES", None),
        ("Parking", lambda a: "✓" if a.listing.features.has_parking else "✗"),
        ("Balcony", lambda a: "✓" if a.listing.features.has_balcony else "✗"),
        ("Terrace", lambda a: "✓" if a.listing.features.has_terrace else "✗"),
        ("Cellar", lambda a: "✓" if a.listing.features.has_cellar else "✗"),
        ("Fireplace", lambda a: "✓" if a.listing.features.has_fireplace else "✗"),
        ("Parquet", lambda a: "✓" if a.listing.features.has_parquet else "✗"),
    ]

    # Calculate column widths
    label_w = 18
    col_w = max(20, 80 // len(analyses))

    # Print header
    header = f"{'Metric':<{label_w}}"
    for i, a in enumerate(analyses, 1):
        header += f" │ {'#' + str(i) + ' ' + a.listing.address.city:<{col_w}}"
    print(header)
    print("─" * len(header))

    # Print rows
    for label, getter in metrics:
        if getter is None:
            if label:
                print(f"\n{label}")
                print("─" * len(header))
            continue

        row = f"{label:<{label_w}}"
        values = [getter(a) for a in analyses]

        for val in values:
            row += f" │ {str(val):<{col_w}}"
        print(row)


def print_recommendation(analyses: list[ListingAnalysis]):
    """Print a recommendation based on the analysis."""
    if not analyses:
        return

    print("\n" + "=" * 100)
    print("💡 RECOMMENDATION")
    print("=" * 100)

    # Find best by different criteria
    best_score = max(analyses, key=lambda x: x.evaluation.overall_score)
    best_value = max(analyses, key=lambda x: x.value_score)
    lowest_price = min(analyses, key=lambda x: x.listing.price_info.price)
    lowest_risk = min(
        analyses,
        key=lambda x: ["🟢", "🟡", "🟠", "🔴"].index(x.evaluation.risk_level.value[0]),
    )

    print(
        f"\n  🏆 BEST OVERALL SCORE: #{best_score.rank} {best_score.listing.address.city}"
    )
    print(
        f"     Score: {best_score.evaluation.overall_score:.0f}/100 | {best_score.evaluation.rating.value}"
    )

    print(
        f"\n  💰 BEST VALUE (Score/Price): #{best_value.rank} {best_value.listing.address.city}"
    )
    print(
        f"     Value Score: {best_value.value_score:.1f} | {best_value.listing.price_info.price:,}€ for {best_value.evaluation.overall_score:.0f} pts"
    )

    print(
        f"\n  💵 LOWEST PRICE: #{lowest_price.rank} {lowest_price.listing.address.city}"
    )
    print(
        f"     Price: {lowest_price.listing.price_info.price:,}€ | {lowest_price.listing.price_per_sqm:,.0f}€/m²"
    )

    print(f"\n  🛡️ LOWEST RISK: #{lowest_risk.rank} {lowest_risk.listing.address.city}")
    print(f"     Risk: {lowest_risk.evaluation.risk_level.value}")

    # Red flags summary (only show if there are any)
    listings_with_flags = [a for a in analyses if a.evaluation.red_flags]
    if listings_with_flags:
        print("\n  🚩 RED FLAGS:")
        for a in listings_with_flags:
            print(
                f"     #{a.rank} {a.listing.address.city}: {', '.join(a.evaluation.red_flags[:2])}"
            )

    # Final verdict
    print("\n  📝 VERDICT:")
    if best_score == best_value:
        print(
            f"     → #{best_score.rank} {best_score.listing.address.city} is both highest quality AND best value!"
        )
    else:
        print(
            f"     → #{best_score.rank} {best_score.listing.address.city} for quality (highest score)"
        )
        print(
            f"     → #{best_value.rank} {best_value.listing.address.city} for value (best bang for buck)"
        )


def add_investment_analysis(
    analyses: list[ListingAnalysis],
    monthly_rent: Optional[float] = None,
    down_payment_pct: float = 20.0,
    loan_duration: int = 20,
    interest_rate: Optional[float] = None,
):
    """Add investment analysis to each listing."""
    analyzer = InvestmentAnalyzer()

    print("\n📈 Running investment analysis...\n")

    for a in analyses:
        l = a.listing
        report = analyzer.analyze(
            purchase_price=l.price_info.price,
            surface_area=l.surface_area,
            city=l.address.city,
            postal_code=l.address.postal_code,
            monthly_rent=monthly_rent,  # Will be estimated if None
            annual_charges=l.price_info.annual_charges,
            annual_property_tax=l.price_info.property_tax,
            description=l.description,
            title=l.title,
            year_built=l.features.year_built,
            condition=l.features.condition,
            has_parking=l.features.has_parking or False,
            has_balcony_terrace=(l.features.has_balcony or l.features.has_terrace)
            or False,
            down_payment_percentage=down_payment_pct,
            loan_duration_years=loan_duration,
            interest_rate=interest_rate,
            include_loan_comparison=True,
        )
        a.investment = report


def print_investment_summary(
    analyses: list[ListingAnalysis],
    loan_duration: int = 25,
    down_payment_pct: float = 20.0,
    interest_rate: float = None,
):
    """Print investment analysis summary for all listings."""
    if not analyses or not any(a.investment for a in analyses):
        print("\n⚠️ No investment analysis available.")
        return

    # Get default interest rate from CashFlowModeler if not specified
    if interest_rate is None:
        from src.financial.cashflow import CashFlowModeler

        interest_rate = CashFlowModeler.DEFAULT_RATES.get(loan_duration, 3.65)

    print("\n" + "=" * 170)
    print("💰 INVESTMENT ANALYSIS SUMMARY")
    print("=" * 170)

    # Print financial assumptions
    print("\n📋 Financial Parameters Used:")
    print(f"   • Loan Duration: {loan_duration} years")
    print(f"   • Down Payment: {down_payment_pct:.0f}%")
    print(f"   • Interest Rate: {interest_rate:.2f}%")
    print(f"   • Loan Insurance: 0.30%/year")
    print(f"   • Vacancy Allowance: 1 month/year")
    print(f"   • Copro Charges: ~3€/m²/month (if not provided)")
    print(f"   • Taxe Foncière: ~1.5 months rent (if not provided)")
    print(f"   • PNO Insurance: 0.2% of property value")
    print("")

    # Header
    print(
        f"{'#':<3} {'City':<15} {'Price':<12} {'Total Cost':<14} "
        f"{'Rent':<10} {'Gross %':<9} {'Net %':<9} {'Cash Flow':<14} {'Status':<14} {'URL'}"
    )
    print("-" * 170)

    for a in analyses:
        if not a.investment:
            continue
        inv = a.investment

        cf_str = (
            f"{'+' if inv.monthly_cash_flow >= 0 else ''}{inv.monthly_cash_flow:,.0f}€"
        )
        rent_str = f"{inv.monthly_rent:,.0f}€" + (" *" if inv.rent_is_estimated else "")

        # Status emoji
        status = inv.cash_flow_status
        if "Positive" in status:
            status_short = "🟢 Positive"
        elif "Break" in status or "Neutral" in status:
            status_short = "🟡 Break-even"
        else:
            status_short = "🔴 Effort req."

        print(
            f"{a.rank:<3} {a.listing.address.city:<15} "
            f"{inv.purchase_price:<12,} {inv.total_acquisition_cost:<14,} "
            f"{rent_str:<10} {inv.gross_yield:<9.2f} {inv.net_yield:<9.2f} "
            f"{cf_str:<14} {status_short:<14} {a.listing.url}"
        )

    print("-" * 170)
    print("* = estimated rent | Yields in % | Cash Flow = monthly")

    # Find best investment
    with_investment = [a for a in analyses if a.investment]
    if with_investment:
        best_yield = max(with_investment, key=lambda x: x.investment.gross_yield)
        best_cf = max(with_investment, key=lambda x: x.investment.monthly_cash_flow)

        print(
            f"\n  📊 BEST GROSS YIELD: #{best_yield.rank} {best_yield.listing.address.city} ({best_yield.investment.gross_yield:.2f}%)"
        )
        print(
            f"  💰 BEST CASH FLOW: #{best_cf.rank} {best_cf.listing.address.city} ({'+' if best_cf.investment.monthly_cash_flow >= 0 else ''}{best_cf.investment.monthly_cash_flow:,.0f}€/month)"
        )


def print_investment_details(analyses: list[ListingAnalysis]):
    """Print detailed investment analysis for each listing."""
    analyzer = InvestmentAnalyzer()

    for a in analyses:
        if not a.investment:
            continue

        print("\n")
        print(analyzer.format_report(a.investment))


def export_to_csv(analyses: list[ListingAnalysis], filename: str):
    """Export comparison data to CSV."""
    if not analyses:
        return

    rows = []
    for a in analyses:
        l = a.listing
        e = a.evaluation
        row = {
            "Rank": a.rank,
            "ID": l.id,
            "Source": l.source,
            "City": l.address.city,
            "Postal": l.address.postal_code,
            "Street": l.address.street or "",
            "Surface_m2": l.surface_area,
            "Price_EUR": l.price_info.price,
            "Price_per_m2": l.price_per_sqm,
            "Annual_Charges": l.price_info.annual_charges or "",
            "Score": e.overall_score,
            "Rating": e.rating.value,
            "Risk": e.risk_level.value,
            "Value_Score": round(a.value_score, 2),
            "Fair_Value_Est": e.fair_value_estimate or "",
            "DPE": l.energy_rating.energy_class.value,
            "GES": l.energy_rating.ges_class.value,
            "Rooms": l.features.rooms or "",
            "Bedrooms": l.features.bedrooms or "",
            "Floor": l.features.floor if l.features.floor is not None else "",
            "Elevator": l.features.has_elevator,
            "Parking": l.features.has_parking,
            "Terrace": l.features.has_terrace,
            "Balcony": l.features.has_balcony,
            "Cellar": l.features.has_cellar,
            "Building_Era": l.features.building_era or "",
            "Condition": l.features.condition or "",
            "Metro_Lines": ",".join(l.transport.metro_lines),
            "Transport_Distance": l.transport.distance_to_transport or "",
            "Copro_Lots": l.building.total_lots or "",
            "Red_Flags": "; ".join(e.red_flags),
            "URL": str(l.url),
        }

        # Add investment data if available
        if a.investment:
            inv = a.investment
            row.update(
                {
                    "Total_Acquisition_Cost": inv.total_acquisition_cost,
                    "Notary_Fees": inv.notary_fees.total_fees,
                    "Monthly_Rent": inv.monthly_rent,
                    "Rent_Estimated": inv.rent_is_estimated,
                    "Gross_Yield": round(inv.gross_yield, 2),
                    "Net_Yield": round(inv.net_yield, 2),
                    "Monthly_Cash_Flow": round(inv.monthly_cash_flow, 0),
                    "Cash_Flow_Status": inv.cash_flow_status,
                }
            )

        rows.append(row)

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Exported to {filename}")


def load_urls_from_cache(cache_path: str) -> list[str]:
    """Load listing URLs from a search cache file.

    Args:
        cache_path: Path to cache file (absolute or relative to SEARCH_CACHE_DIR)

    Returns:
        List of listing URLs
    """
    path = Path(cache_path)

    # Try as-is first, then in cache directory
    if not path.exists():
        path = SEARCH_CACHE_DIR / cache_path

    if not path.exists():
        raise FileNotFoundError(f"Cache file not found: {cache_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    urls = data.get("listings", [])
    if not urls:
        raise ValueError(f"No listings found in cache file: {cache_path}")

    # Print cache info
    meta = data.get("metadata", {})
    print(f"📂 Loading from cache: {path.name}")
    print(f"   Search URL: {meta.get('search_url', 'unknown')[:60]}...")
    print(f"   Fetched at: {meta.get('fetched_at', 'unknown')}")
    print(f"   Total listings: {len(urls)}")

    return urls


def main():
    parser = argparse.ArgumentParser(
        description="Compare and rank French real estate listings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "urls",
        nargs="*",
        help="URLs of listings to compare (not needed if using --from-cache)",
    )
    parser.add_argument(
        "--from-cache",
        "-f",
        metavar="FILE",
        help="Load listing URLs from a search cache file (from search_seloger.py)",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Limit number of listings to compare (useful with --from-cache)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["requests", "cloudscraper", "simple", "headless"],
        default=None,
        help="Fetch mode (default: auto-detect per site - PAP uses cloudscraper, SeLoger uses requests)",
    )
    parser.add_argument(
        "--sort",
        "-s",
        choices=["score", "price", "price_m2", "surface", "value", "yield"],
        default="score",
        help="Sort listings by: score, price, price_m2, surface, value, yield (default: score)",
    )
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed side-by-side comparison",
    )
    parser.add_argument(
        "--investment",
        "-i",
        action="store_true",
        help="Show investment analysis (yield, cash flow, notary fees)",
    )
    parser.add_argument(
        "--investment-detailed",
        action="store_true",
        help="Show full investment report for each listing",
    )
    parser.add_argument(
        "--rent",
        type=float,
        default=None,
        help="Expected monthly rent for investment analysis (estimated if not provided)",
    )
    parser.add_argument(
        "--down-payment",
        type=float,
        default=20.0,
        help="Down payment percentage (default: 20%%)",
    )
    parser.add_argument(
        "--loan-duration",
        type=int,
        default=25,
        choices=[15, 20, 25],
        help="Loan duration in years (default: 25)",
    )
    parser.add_argument(
        "--interest-rate",
        type=float,
        default=None,
        help="Annual interest rate (default: current market rate ~3.5%%)",
    )
    parser.add_argument(
        "--export",
        "-e",
        metavar="FILE",
        help="Export comparison to CSV file",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable cache, always fetch fresh data from network",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="Include listings with red flags (by default, only clean listings are shown)",
    )
    parser.add_argument(
        "--max-commute",
        type=int,
        default=None,
        metavar="MINUTES",
        help="Filter listings by max commute time to Paris (e.g., --max-commute 30)",
    )

    args = parser.parse_args()

    # Get URLs from cache or command line
    urls = []
    if args.from_cache:
        try:
            urls = load_urls_from_cache(args.from_cache)
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            print(f"\n💡 Available cache files in {SEARCH_CACHE_DIR}:")
            if SEARCH_CACHE_DIR.exists():
                for f in sorted(SEARCH_CACHE_DIR.glob("*.json"))[:10]:
                    print(f"   {f.name}")
            sys.exit(1)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"❌ Error reading cache: {e}")
            sys.exit(1)
    else:
        urls = args.urls

    if not urls:
        parser.error("Please provide listing URLs or use --from-cache")

    # Apply limit if specified
    if args.limit and args.limit > 0:
        if len(urls) > args.limit:
            print(f"   Limiting to first {args.limit} of {len(urls)} listings")
        urls = urls[: args.limit]

    # Analyze listings
    analyses = analyze_listings(urls, args.mode, use_cache=not args.no_cache)

    if not analyses:
        print("\n❌ No listings could be analyzed.")
        sys.exit(1)

    # Filter out listings with red flags (unless --include-all is specified)
    if not args.include_all:
        total_before = len(analyses)
        analyses = [a for a in analyses if not a.evaluation.red_flags]
        filtered_count = total_before - len(analyses)
        if filtered_count > 0:
            print(f"\n🔍 Filtered out {filtered_count} listings with red flags")
            print(
                f"   → Showing {len(analyses)} clean listings (use --include-all to see all)"
            )

        if not analyses:
            print("\n❌ No clean listings remaining after filtering.")
            print(
                "   Use --include-all to see all listings including those with red flags."
            )
            sys.exit(1)

    # Filter out listings outside Île-de-France
    IDF_DEPARTMENTS = {"75", "77", "78", "91", "92", "93", "94", "95"}
    total_before = len(analyses)
    idf_analyses = []
    non_idf = []
    for a in analyses:
        postal = a.listing.address.postal_code or ""
        dept = postal[:2]
        if dept in IDF_DEPARTMENTS:
            idf_analyses.append(a)
        else:
            non_idf.append(f"{a.listing.address.city} ({postal})")

    if non_idf:
        print(f"\n🗺️  Filtered out {len(non_idf)} listings outside Île-de-France:")
        for city in non_idf[:5]:
            print(f"   → {city}")
        if len(non_idf) > 5:
            print(f"   → ... and {len(non_idf) - 5} more")
        analyses = idf_analyses

    if not analyses:
        print("\n❌ No listings in Île-de-France found.")
        sys.exit(1)

    # Filter out listings with Unknown city
    total_before = len(analyses)
    known_city_analyses = []
    unknown_cities = []
    for a in analyses:
        city = a.listing.address.city or ""
        if city.lower() == "unknown" or not city:
            unknown_cities.append(a.listing.address.postal_code or "no postal")
        else:
            known_city_analyses.append(a)

    if unknown_cities:
        print(f"\n❓ Filtered out {len(unknown_cities)} listings with unknown city")
        analyses = known_city_analyses

    if not analyses:
        print("\n❌ No listings with known cities found.")
        sys.exit(1)

    # Filter by commute time if specified
    if args.max_commute:
        evaluator = FrenchRealEstateEvaluator()
        total_before = len(analyses)
        filtered_analyses = []
        for a in analyses:
            commute = evaluator.get_commute_time(
                a.listing.address.city, a.listing.address.postal_code
            )
            if commute is not None and commute <= args.max_commute:
                filtered_analyses.append(a)

        filtered_count = total_before - len(filtered_analyses)
        analyses = filtered_analyses

        if filtered_count > 0:
            print(
                f"\n🚇 Filtered out {filtered_count} listings with commute > {args.max_commute}min"
            )
            print(
                f"   → Showing {len(analyses)} listings within {args.max_commute}min of Paris"
            )

        if not analyses:
            print(f"\n❌ No listings found with commute time ≤ {args.max_commute}min.")
            print("   Try increasing --max-commute or removing the filter.")
            sys.exit(1)

    # Run investment analysis if requested or if sorting by yield
    run_investment = args.investment or args.investment_detailed or args.sort == "yield"
    if run_investment:
        add_investment_analysis(
            analyses,
            monthly_rent=args.rent,
            down_payment_pct=args.down_payment,
            loan_duration=args.loan_duration,
            interest_rate=args.interest_rate,
        )

    # Sort by yield if requested (requires investment analysis)
    if args.sort == "yield" and all(a.investment for a in analyses):
        analyses.sort(key=lambda x: x.investment.gross_yield, reverse=True)
        for i, a in enumerate(analyses, 1):
            a.rank = i

    # Sort by cash flow for investment reports (positive first, then by amount)
    cash_flow_sorted = False
    if run_investment and args.sort == "score":
        # Default to cash flow sort for investment reports
        analyses.sort(
            key=lambda x: (
                x.investment.monthly_cash_flow if x.investment else float("-inf")
            ),
            reverse=True,
        )
        # Re-assign ranks after sorting by cash flow
        for i, a in enumerate(analyses, 1):
            a.rank = i
        cash_flow_sorted = True

    # Print summary table (skip_sort=True if we already sorted by cash flow or yield)
    sort_display = "cash flow" if cash_flow_sorted else args.sort
    print_summary_table(
        analyses, sort_display, skip_sort=(cash_flow_sorted or args.sort == "yield")
    )

    # Print detailed comparison if requested or if only 2 listings
    if args.detailed or len(analyses) == 2:
        print_detailed_comparison(analyses)

    # Print recommendation
    if len(analyses) >= 2:
        print_recommendation(analyses)

    # Print investment summary if requested
    if run_investment:
        print_investment_summary(
            analyses,
            loan_duration=args.loan_duration,
            down_payment_pct=args.down_payment,
            interest_rate=args.interest_rate,
        )

        # Print detailed investment reports if requested
        if args.investment_detailed:
            print_investment_details(analyses)

    # Export if requested
    if args.export:
        export_to_csv(analyses, args.export)

    print()


if __name__ == "__main__":
    main()
