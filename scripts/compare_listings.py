#!/usr/bin/env python3
"""Compare and rank French real estate listings.

This script helps you:
1. Compare multiple listings side-by-side
2. Rank them by overall score and value metrics
3. Identify the "best" options based on your criteria

Usage:
    # Compare two listings
    python scripts/compare_listings.py URL1 URL2

    # Compare multiple listings
    python scripts/compare_listings.py URL1 URL2 URL3 URL4

    # Rank by specific criteria
    python scripts/compare_listings.py URL1 URL2 --sort price
    python scripts/compare_listings.py URL1 URL2 --sort score
    python scripts/compare_listings.py URL1 URL2 --sort value

    # Show detailed comparison
    python scripts/compare_listings.py URL1 URL2 --detailed

    # Export to CSV for spreadsheet analysis
    python scripts/compare_listings.py URL1 URL2 --export comparison.csv
"""

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.evaluation import EvaluationResult, FrenchRealEstateEvaluator
from src.models.listing import Listing
from src.scraper import FetchMode, get_scraper


@dataclass
class ListingAnalysis:
    """Combined listing data and evaluation."""

    listing: Listing
    evaluation: EvaluationResult
    rank: int = 0

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


def fetch_listing(url: str, mode: str = "requests") -> Optional[Listing]:
    """Fetch and parse a listing from URL."""
    fetch_mode = {
        "requests": FetchMode.REQUESTS,
        "simple": FetchMode.SIMPLE,
        "headless": FetchMode.HEADLESS,
    }.get(mode, FetchMode.REQUESTS)

    try:
        scraper = get_scraper(url, mode=fetch_mode)
        listing = scraper.extract(url)
        scraper.close()
        return listing
    except Exception as e:
        print(f"  ✗ Error fetching: {e}")
        return None


def analyze_listings(urls: list[str], mode: str = "requests") -> list[ListingAnalysis]:
    """Fetch, parse and evaluate multiple listings."""
    evaluator = FrenchRealEstateEvaluator()
    analyses = []

    print("\n📊 Fetching and analyzing listings...\n")

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {url[:60]}...")
        listing = fetch_listing(url, mode)
        if listing:
            evaluation = evaluator.evaluate(listing)
            analyses.append(ListingAnalysis(listing=listing, evaluation=evaluation))
            print(
                f"        ✓ {listing.address.city} - {listing.surface_area}m² - {listing.price_info.price:,}€"
            )
        else:
            print(f"        ✗ Failed to fetch")

    return analyses


def print_summary_table(analyses: list[ListingAnalysis], sort_by: str = "score"):
    """Print a compact summary table of all listings."""
    if not analyses:
        print("\n⚠️ No listings to compare.")
        return

    # Sort analyses
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

    print("\n" + "=" * 100)
    print("📋 LISTING COMPARISON SUMMARY")
    print("=" * 100)

    # Header
    print(
        f"{'#':<3} {'City':<15} {'Surface':<10} {'Price':<12} {'€/m²':<10} "
        f"{'Score':<8} {'Rating':<8} {'Risk':<12} {'DPE':<5} {'Value':<8}"
    )
    print("-" * 100)

    # Rows
    for a in analyses:
        l = a.listing
        e = a.evaluation

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
            f"{prefix}{a.rank:<2} {l.address.city:<15} {l.surface_area:<10.0f} "
            f"{l.price_info.price:<12,} {l.price_per_sqm:<10,.0f} "
            f"{e.overall_score:<8.0f} {e.rating.value:<8} {risk_short:<12} "
            f"{l.energy_rating.energy_class.value:<5} {a.value_score:<8.1f}"
        )

    print("-" * 100)
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

    # Red flags summary
    print("\n  🚩 RED FLAGS BY LISTING:")
    for a in analyses:
        if a.evaluation.red_flags:
            print(
                f"     #{a.rank} {a.listing.address.city}: {', '.join(a.evaluation.red_flags[:2])}"
            )
        else:
            print(f"     #{a.rank} {a.listing.address.city}: None ✓")

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


def export_to_csv(analyses: list[ListingAnalysis], filename: str):
    """Export comparison data to CSV."""
    if not analyses:
        return

    rows = []
    for a in analyses:
        l = a.listing
        e = a.evaluation
        rows.append(
            {
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
        )

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Exported to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare and rank French real estate listings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "urls",
        nargs="+",
        help="URLs of listings to compare (at least 1, preferably 2+)",
    )
    parser.add_argument(
        "--mode",
        "-m",
        choices=["requests", "simple", "headless"],
        default="requests",
        help="Fetch mode (default: requests)",
    )
    parser.add_argument(
        "--sort",
        "-s",
        choices=["score", "price", "price_m2", "surface", "value"],
        default="score",
        help="Sort listings by: score, price, price_m2, surface, value (default: score)",
    )
    parser.add_argument(
        "--detailed",
        "-d",
        action="store_true",
        help="Show detailed side-by-side comparison",
    )
    parser.add_argument(
        "--export",
        "-e",
        metavar="FILE",
        help="Export comparison to CSV file",
    )

    args = parser.parse_args()

    if len(args.urls) < 1:
        parser.error("Please provide at least one listing URL")

    # Analyze listings
    analyses = analyze_listings(args.urls, args.mode)

    if not analyses:
        print("\n❌ No listings could be analyzed.")
        sys.exit(1)

    # Print summary table
    print_summary_table(analyses, args.sort)

    # Print detailed comparison if requested or if only 2 listings
    if args.detailed or len(analyses) == 2:
        print_detailed_comparison(analyses)

    # Print recommendation
    if len(analyses) >= 2:
        print_recommendation(analyses)

    # Export if requested
    if args.export:
        export_to_csv(analyses, args.export)

    print()


if __name__ == "__main__":
    main()
