"""French Real Estate Evaluation Protocol.

This module implements a comprehensive evaluation system for French real estate
listings based on key criteria that affect property value and investment risk.

Evaluation Hierarchy (in order of importance):
1. Loi Carrez vs Total Surface - Legal compliance and accurate pricing
2. DPE (Energy Performance) - Rental legality and future costs
3. Location & Micro-Quartier - Transport, nuisances, future value
4. Building Health (Copropriété) - HOA charges and surprise costs
5. Intrinsic Features (Plus-Value) - Floor, orientation, layout
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.models.listing import EnergyClass, Listing


class Rating(str, Enum):
    """Overall listing rating."""

    EXCELLENT = "★★★★★"  # 90-100 points
    GOOD = "★★★★☆"  # 75-89 points
    AVERAGE = "★★★☆☆"  # 60-74 points
    BELOW_AVG = "★★☆☆☆"  # 40-59 points
    POOR = "★☆☆☆☆"  # 0-39 points


class RiskLevel(str, Enum):
    """Investment risk level."""

    LOW = "🟢 Low Risk"
    MEDIUM = "🟡 Medium Risk"
    HIGH = "🟠 High Risk"
    CRITICAL = "🔴 Critical Risk"


@dataclass
class CriterionScore:
    """Score for a single evaluation criterion."""

    name: str
    category: str
    score: float  # 0-100
    max_score: float
    weight: float  # Importance weight (0-1)
    status: str  # ✅ ⚠️ ❌ ❓
    details: str
    recommendations: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Complete evaluation result for a listing."""

    listing_id: str
    overall_score: float  # 0-100
    rating: Rating
    risk_level: RiskLevel
    criteria: list[CriterionScore]
    fair_value_estimate: Optional[float]
    negotiation_margin: Optional[float]  # Suggested discount %
    summary: str
    red_flags: list[str]
    green_flags: list[str]

    def to_report(self) -> str:
        """Generate a formatted evaluation report."""
        lines = [
            "=" * 60,
            "FRENCH REAL ESTATE EVALUATION REPORT",
            "=" * 60,
            "",
            f"Listing ID: {self.listing_id}",
            f"Overall Score: {self.overall_score:.0f}/100",
            f"Rating: {self.rating.value}",
            f"Risk Level: {self.risk_level.value}",
            "",
        ]

        if self.fair_value_estimate:
            lines.append(f"Estimated Fair Value: {self.fair_value_estimate:,.0f} €")
        if self.negotiation_margin:
            lines.append(f"Suggested Negotiation: -{self.negotiation_margin:.0f}%")

        lines.extend(
            ["", "-" * 60, "EVALUATION BY CRITERIA (Order of Importance)", "-" * 60, ""]
        )

        for i, criterion in enumerate(self.criteria, 1):
            lines.extend(
                [
                    f"{i}. {criterion.category.upper()}: {criterion.name}",
                    f"   {criterion.status} Score: {criterion.score:.0f}/{criterion.max_score:.0f} (Weight: {criterion.weight*100:.0f}%)",
                    f"   {criterion.details}",
                ]
            )
            for rec in criterion.recommendations:
                lines.append(f"   → {rec}")
            lines.append("")

        if self.red_flags:
            lines.extend(["-" * 60, "🚩 RED FLAGS", "-" * 60])
            for flag in self.red_flags:
                lines.append(f"  • {flag}")
            lines.append("")

        if self.green_flags:
            lines.extend(["-" * 60, "✅ GREEN FLAGS", "-" * 60])
            for flag in self.green_flags:
                lines.append(f"  • {flag}")
            lines.append("")

        lines.extend(["-" * 60, "SUMMARY", "-" * 60, self.summary, "=" * 60])

        return "\n".join(lines)


class FrenchRealEstateEvaluator:
    """Evaluator for French real estate listings.

    Implements the French real estate evaluation protocol based on:
    1. Loi Carrez compliance
    2. DPE energy performance
    3. Location quality
    4. Building (copropriété) health
    5. Intrinsic features
    """

    # Average price per m² by department (simplified - would be more granular in production)
    AVG_PRICES_PER_M2 = {
        "75": 10500,  # Paris
        "92": 6500,  # Hauts-de-Seine
        "93": 4000,  # Seine-Saint-Denis
        "94": 5500,  # Val-de-Marne
        "69": 4500,  # Lyon
        "13": 3500,  # Marseille
        "default": 3500,
    }

    # DPE rental ban schedule
    DPE_BAN_SCHEDULE = {
        EnergyClass.G: 2025,
        EnergyClass.F: 2028,
        EnergyClass.E: 2034,
    }

    # Weight factors for each criterion category
    WEIGHTS = {
        "surface": 0.20,  # Loi Carrez
        "energy": 0.25,  # DPE - highest weight due to rental bans
        "location": 0.20,  # Location & transport
        "building": 0.20,  # Copropriété health
        "features": 0.15,  # Intrinsic features
    }

    def evaluate(self, listing: Listing) -> EvaluationResult:
        """Evaluate a listing and return comprehensive results."""
        criteria = []
        red_flags = []
        green_flags = []
        recommendations = []

        # Check for suspicious pricing first
        self._check_suspicious_price(listing, red_flags, recommendations)

        # Check for VEFA (off-plan properties)
        self._check_vefa(listing, red_flags, recommendations)

        # 1. Surface & Loi Carrez
        surface_score = self._evaluate_surface(listing, red_flags, green_flags)
        criteria.append(surface_score)

        # 2. DPE Energy Performance
        energy_score = self._evaluate_energy(listing, red_flags, green_flags)
        criteria.append(energy_score)

        # 3. Location & Transport
        location_score = self._evaluate_location(listing, red_flags, green_flags)
        criteria.append(location_score)

        # 4. Building Health (Copropriété)
        building_score = self._evaluate_building(listing, red_flags, green_flags)
        criteria.append(building_score)

        # 5. Intrinsic Features
        features_score = self._evaluate_features(listing, red_flags, green_flags)
        criteria.append(features_score)

        # Calculate overall score
        overall_score = sum(c.score * c.weight for c in criteria)

        # Determine rating
        rating = self._score_to_rating(overall_score)

        # Determine risk level
        risk_level = self._determine_risk(listing, red_flags)

        # Calculate fair value estimate
        fair_value = self._estimate_fair_value(listing)

        # Calculate negotiation margin
        negotiation = self._calculate_negotiation_margin(
            listing, energy_score, building_score
        )

        # Generate summary
        summary = self._generate_summary(listing, overall_score, red_flags, green_flags)

        return EvaluationResult(
            listing_id=listing.id,
            overall_score=overall_score,
            rating=rating,
            risk_level=risk_level,
            criteria=criteria,
            fair_value_estimate=fair_value,
            negotiation_margin=negotiation,
            summary=summary,
            red_flags=red_flags,
            green_flags=green_flags,
        )

    def _evaluate_surface(
        self, listing: Listing, red_flags: list, green_flags: list
    ) -> CriterionScore:
        """Evaluate Loi Carrez surface compliance."""
        score = 100.0
        details = []
        recommendations = []
        status = "✅"

        surface = listing.surface_area
        carrez = listing.carrez_area

        # Check if Carrez surface is provided
        if carrez:
            if carrez < surface:
                diff_pct = ((surface - carrez) / surface) * 100
                details.append(
                    f"Carrez: {carrez}m² vs Advertised: {surface}m² ({diff_pct:.1f}% difference)"
                )

                if diff_pct > 10:
                    score -= 30
                    status = "⚠️"
                    recommendations.append(
                        f"Calculate price based on Carrez surface ({carrez}m²), not advertised"
                    )
                    red_flags.append(
                        f"Large surface discrepancy: {diff_pct:.1f}% non-Carrez space"
                    )
                elif diff_pct > 5:
                    score -= 15
                    recommendations.append(
                        "Verify what the non-Carrez space includes (balcony, low ceiling areas)"
                    )
            else:
                details.append(f"Carrez surface: {carrez}m² (matches advertised)")
                green_flags.append("Carrez surface matches advertised surface")
        else:
            score -= 10
            status = "❓"
            details.append(f"Surface: {surface}m² (Carrez not specified)")
            recommendations.append(
                "Request official Loi Carrez measurement before making an offer"
            )

        # Check price per m² reasonableness
        price_per_m2 = listing.price_per_sqm
        details.append(f"Price/m²: {price_per_m2:,.0f}€")

        return CriterionScore(
            name="Loi Carrez Compliance",
            category="Surface",
            score=score,
            max_score=100,
            weight=self.WEIGHTS["surface"],
            status=status,
            details=" | ".join(details),
            recommendations=recommendations,
        )

    def _evaluate_energy(
        self, listing: Listing, red_flags: list, green_flags: list
    ) -> CriterionScore:
        """Evaluate DPE energy performance."""
        score = 100.0
        details = []
        recommendations = []
        status = "✅"

        dpe = listing.energy_rating.energy_class
        ges = listing.energy_rating.ges_class

        # DPE scoring
        dpe_scores = {
            EnergyClass.A: (100, "Excellent energy efficiency"),
            EnergyClass.B: (90, "Very good energy efficiency"),
            EnergyClass.C: (80, "Good energy efficiency"),
            EnergyClass.D: (65, "Average energy efficiency"),
            EnergyClass.E: (40, "Poor efficiency - Rental ban 2034"),
            EnergyClass.F: (20, "Very poor - Rental ban 2028"),
            EnergyClass.G: (0, "Critical - BANNED from rental since 2025"),
            EnergyClass.UNKNOWN: (50, "DPE not provided - Request it"),
        }

        dpe_score, dpe_desc = dpe_scores.get(dpe, (50, "Unknown"))
        score = dpe_score
        details.append(f"DPE: {dpe.value} - {dpe_desc}")

        # Check for rental ban risk
        if dpe in self.DPE_BAN_SCHEDULE:
            ban_year = self.DPE_BAN_SCHEDULE[dpe]
            if ban_year <= 2025:
                status = "❌"
                red_flags.append(f"DPE {dpe.value}: ALREADY BANNED from rental market!")
                recommendations.append("This property CANNOT be legally rented")
                recommendations.append("Budget €15,000-40,000 for energy renovation")
            else:
                status = "⚠️"
                red_flags.append(
                    f"DPE {dpe.value}: Will be banned from rental in {ban_year}"
                )
                recommendations.append(
                    f"Negotiate 10-15% discount to cover insulation costs"
                )
                recommendations.append("Get renovation quotes before purchasing")
        elif dpe == EnergyClass.UNKNOWN:
            status = "❓"
            recommendations.append(
                "Request DPE before proceeding - it's legally required"
            )
        elif dpe in [EnergyClass.A, EnergyClass.B]:
            green_flags.append(f"Excellent energy rating ({dpe.value})")

        # GES (greenhouse gas)
        if ges != EnergyClass.UNKNOWN:
            details.append(f"GES: {ges.value}")

        return CriterionScore(
            name="Energy Performance (DPE)",
            category="Energy",
            score=score,
            max_score=100,
            weight=self.WEIGHTS["energy"],
            status=status,
            details=" | ".join(details),
            recommendations=recommendations,
        )

    # Average market prices per m² by department (approximate 2024-2025)
    # Used to detect suspiciously low prices
    AVG_PRICE_PER_SQM = {
        "75": 10500,  # Paris
        "92": 6500,  # Hauts-de-Seine
        "93": 4200,  # Seine-Saint-Denis
        "94": 5200,  # Val-de-Marne
        "91": 3200,  # Essonne
        "95": 3500,  # Val-d'Oise
        "77": 3000,  # Seine-et-Marne
        "78": 4200,  # Yvelines
    }

    # Threshold for suspicious price (percentage of average)
    SUSPICIOUS_PRICE_THRESHOLD = 0.70  # Flag if < 70% of average

    def _check_suspicious_price(
        self, listing: Listing, red_flags: list, recommendations: list
    ) -> bool:
        """Check if the price is suspiciously low for the area.
        
        Returns True if the price is suspicious.
        """
        postal = listing.address.postal_code or ""
        dept = postal[:2] if postal else ""
        
        avg_price = self.AVG_PRICE_PER_SQM.get(dept)
        if not avg_price:
            return False
        
        price_per_sqm = listing.price_per_sqm
        if not price_per_sqm or price_per_sqm <= 0:
            return False
        
        threshold = avg_price * self.SUSPICIOUS_PRICE_THRESHOLD
        
        if price_per_sqm < threshold:
            pct_of_avg = (price_per_sqm / avg_price) * 100
            red_flags.append(
                f"Suspiciously low price ({price_per_sqm:,.0f}€/m² = {pct_of_avg:.0f}% of avg {avg_price:,}€/m²)"
            )
            recommendations.append(
                "⚠️ Price significantly below market - verify condition, location, legal issues"
            )
            recommendations.append(
                "Check for: viager, occupied property, major works needed, flood zone, noise"
            )
            return True
        
        return False

    def _check_vefa(
        self, listing: Listing, red_flags: list, recommendations: list
    ) -> bool:
        """Check if the property is VEFA (off-plan, not yet built).
        
        Returns True if the property is VEFA with future delivery.
        Does NOT flag if property is "disponible dès maintenant" (available now).
        """
        import re
        
        # Check title and description for VEFA indicators
        title = (listing.title or "").lower()
        description = (listing.description or "").lower()
        text = f"{title} {description}"
        
        # Check if property is available now - if so, don't flag even if VEFA
        # (property is ready or almost ready for handover)
        immediate_availability = [
            "disponible dès maintenant",
            "disponible des maintenant",
            "disponible immédiatement", 
            "disponible immediatement",
            "disponible de suite",
            "livraison immédiate",
            "livraison immediate",
            "prêt à emménager",
            "pret a emmenager",
        ]
        
        for phrase in immediate_availability:
            if phrase in text:
                # Property is available now, don't flag as VEFA
                return False
        
        # Strong VEFA indicators (definitely off-plan)
        vefa_indicators = [
            "vefa",
            "livraison 202",  # Livraison 2025, 2026, 2027...
            "livraison t",    # Livraison T1, T2, T3, T4
            "livraison prévue",
            "en cours de construction",
            "en cours d'achèvement",
            "programme neuf",
            "programme immobilier neuf",
            "futur achèvement",
            "sur plan",
            "achat sur plan",
            "bien en construction",
            "l'état futur d'achèvement",
            "état futur d'achèvement",
        ]
        
        for indicator in vefa_indicators:
            if indicator in text:
                red_flags.append(
                    f"VEFA (off-plan) - Property not yet built"
                )
                recommendations.append(
                    "⚠️ This is an off-plan purchase - property may not be built yet"
                )
                recommendations.append(
                    "Consider: construction delays, developer bankruptcy risk, final product differences"
                )
                return True
        
        # Check for "disponible à partir de [future date]" pattern
        # This indicates property not yet available
        disponible_match = re.search(
            r"disponible\s+(?:à\s+partir\s+(?:de\s+|du\s+)?|dès\s+le\s+)?"
            r"(t[1-4]\s*20\d{2}|20\d{2}|"
            r"(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+20\d{2})",
            text
        )
        if disponible_match:
            red_flags.append(
                f"VEFA (off-plan) - Property not yet built"
            )
            return True
        
        # Check for future delivery dates in format "livraison 2025" etc
        delivery_match = re.search(r"livraison\s*(?:prévue\s*)?(?:en\s*)?(\d{4}|t[1-4]\s*\d{4})", text)
        if delivery_match:
            red_flags.append(
                f"VEFA (off-plan) - Property not yet built"
            )
            return True
        
        return False

    # Approximate commute times to central Paris (in minutes)
    # Based on RER/Metro/Transilien typical journey times
    COMMUTE_TIMES = {
        # Paris (75) - 5-15 min depending on arrondissement
        "paris": 10,
        # 92 - Hauts-de-Seine (Petite Couronne West)
        "boulogne-billancourt": 15,
        "boulogne billancourt": 15,
        "issy-les-moulineaux": 15,
        "issy les moulineaux": 15,
        "vanves": 18,
        "malakoff": 18,
        "montrouge": 15,
        "clamart": 25,
        "meudon": 22,
        "sèvres": 25,
        "sevres": 25,
        "saint-cloud": 20,
        "saint cloud": 20,
        "suresnes": 20,
        "puteaux": 15,
        "courbevoie": 18,
        "la défense": 15,
        "la defense": 15,
        "nanterre": 20,
        "rueil-malmaison": 25,
        "rueil malmaison": 25,
        "colombes": 20,
        "bois-colombes": 18,
        "bois colombes": 18,
        "asnières": 18,
        "asnieres": 18,
        "gennevilliers": 22,
        "clichy": 15,
        "levallois-perret": 12,
        "levallois perret": 12,
        "neuilly-sur-seine": 12,
        "neuilly sur seine": 12,
        "antony": 25,
        "châtenay-malabry": 30,
        "chatenay-malabry": 30,
        "le plessis-robinson": 30,
        "sceaux": 25,
        "bourg-la-reine": 22,
        "fontenay-aux-roses": 25,
        "châtillon": 20,
        "chatillon": 20,
        # 93 - Seine-Saint-Denis (Petite Couronne North-East)
        "saint-denis": 15,
        "saint denis": 15,
        "aubervilliers": 15,
        "pantin": 12,
        "le pré-saint-gervais": 15,
        "les lilas": 15,
        "bagnolet": 15,
        "montreuil": 18,
        "romainville": 18,
        "noisy-le-sec": 20,
        "noisy le sec": 20,
        "bobigny": 20,
        "bondy": 22,
        "rosny-sous-bois": 22,
        "villemomble": 25,
        "gagny": 28,
        "le raincy": 25,
        "livry-gargan": 30,
        "aulnay-sous-bois": 28,
        "aulnay sous bois": 28,
        "sevran": 30,
        "villepinte": 32,
        "tremblay-en-france": 35,
        "le bourget": 20,
        "drancy": 20,
        "blanc-mesnil": 25,
        "stains": 22,
        "pierrefitte": 25,
        "épinay-sur-seine": 22,
        "saint-ouen": 15,
        "l'île-saint-denis": 18,
        # 94 - Val-de-Marne (Petite Couronne South-East)
        "vincennes": 12,
        "saint-mandé": 12,
        "saint mande": 12,
        "charenton-le-pont": 15,
        "charenton le pont": 15,
        "ivry-sur-seine": 15,
        "ivry sur seine": 15,
        "vitry-sur-seine": 20,
        "vitry sur seine": 20,
        "villejuif": 20,
        "kremlin-bicêtre": 18,
        "kremlin bicetre": 18,
        "cachan": 22,
        "arcueil": 20,
        "gentilly": 15,
        "alfortville": 18,
        "maisons-alfort": 18,
        "maisons alfort": 18,
        "créteil": 25,
        "creteil": 25,
        "saint-maur-des-fossés": 25,
        "joinville-le-pont": 20,
        "nogent-sur-marne": 20,
        "le perreux-sur-marne": 22,
        "fontenay-sous-bois": 18,
        "champigny-sur-marne": 25,
        "chennevières": 30,
        "orly": 25,
        "choisy-le-roi": 22,
        "thiais": 25,
        "rungis": 28,
        "chevilly-larue": 25,
        "villeneuve-saint-georges": 28,
        "valenton": 30,
        "boissy-saint-léger": 28,
        "boissy saint leger": 28,
        "sucy-en-brie": 30,
        "bonneuil-sur-marne": 28,
        # 77 - Seine-et-Marne (Grande Couronne East)
        "chelles": 25,
        "vaires-sur-marne": 28,
        "torcy": 30,
        "lognes": 32,
        "noisiel": 30,
        "bussy-saint-georges": 35,
        "bussy saint georges": 35,
        "marne-la-vallée": 35,
        "marne la vallee": 35,
        "chessy": 40,
        "val d'europe": 40,
        "lagny-sur-marne": 35,
        "lagny": 35,
        "meaux": 45,
        "melun": 50,
        "fontainebleau": 60,
        "pontault-combault": 35,
        "roissy-en-brie": 35,
        "ozoir-la-ferrière": 40,
        "villeparisis": 30,
        "mitry-mory": 35,
        "claye-souilly": 40,
        # 78 - Yvelines (Grande Couronne West)
        "versailles": 25,
        "le chesnay": 28,
        "saint-germain-en-laye": 25,
        "saint germain en laye": 25,
        "poissy": 30,
        "achères": 35,
        "acheres": 35,
        "maisons-laffitte": 25,
        "maisons laffitte": 25,
        "sartrouville": 22,
        "houilles": 20,
        "chatou": 20,
        "le vésinet": 22,
        "le vesinet": 22,
        "conflans-sainte-honorine": 35,
        "conflans sainte honorine": 35,
        "mantes-la-jolie": 50,
        "les mureaux": 45,
        "vélizy-villacoublay": 30,
        "velizy": 30,
        "viroflay": 25,
        "chaville": 22,
        "saint-cyr-l'école": 30,
        "fontenay-le-fleury": 35,
        "plaisir": 40,
        "trappes": 40,
        "rambouillet": 55,
        "montigny-le-bretonneux": 35,
        "guyancourt": 35,
        "élancourt": 40,
        # 91 - Essonne (Grande Couronne South)
        "massy": 25,
        "palaiseau": 30,
        "orsay": 35,
        "gif-sur-yvette": 40,
        "saclay": 40,
        "les ulis": 35,
        "bures-sur-yvette": 35,
        "évry": 40,
        "evry": 40,
        "corbeil-essonnes": 40,
        "savigny-sur-orge": 30,
        "juvisy-sur-orge": 25,
        "athis-mons": 25,
        "viry-châtillon": 30,
        "brétigny-sur-orge": 35,
        "arpajon": 40,
        "saint-michel-sur-orge": 35,
        "sainte-geneviève-des-bois": 35,
        "longjumeau": 30,
        "chilly-mazarin": 28,
        "draveil": 30,
        "vigneux-sur-seine": 28,
        "montgeron": 28,
        "yerres": 30,
        "brunoy": 30,
        "épinay-sous-sénart": 35,
        "saint-chéron": 45,
        "saint cheron": 45,
        "étampes": 55,
        "etampes": 55,
        # 95 - Val-d'Oise (Grande Couronne North)
        "argenteuil": 20,
        "bezons": 22,
        "cergy": 40,
        "pontoise": 40,
        "cergy-pontoise": 40,
        "enghien-les-bains": 18,
        "montmorency": 25,
        "ermont": 22,
        "eaubonne": 25,
        "saint-gratien": 22,
        "franconville": 25,
        "sannois": 22,
        "taverny": 30,
        "herblay": 30,
        "cormeilles-en-parisis": 28,
        "montigny-lès-cormeilles": 25,
        "saint-ouen-l'aumône": 35,
        "osny": 40,
        "goussainville": 30,
        "gonesse": 25,
        "sarcelles": 25,
        "garges-lès-gonesse": 25,
        "villiers-le-bel": 28,
        "arnouville": 28,
        "roissy-en-france": 35,
        "louvres": 35,
    }

    def get_commute_time(self, city: str, postal_code: str = "") -> Optional[int]:
        """Get approximate commute time to Paris in minutes.

        Returns None if city is not in the database.
        """
        if not city:
            return None

        city_lower = city.lower().strip()

        # Direct match
        if city_lower in self.COMMUTE_TIMES:
            return self.COMMUTE_TIMES[city_lower]

        # Partial match (for variations like "Paris 15ème")
        for known_city, time in self.COMMUTE_TIMES.items():
            if known_city in city_lower or city_lower in known_city:
                return time

        # Estimate based on department if no match
        dept = postal_code[:2] if postal_code else ""
        dept_estimates = {
            "75": 15,  # Paris
            "92": 20,  # Hauts-de-Seine
            "93": 22,  # Seine-Saint-Denis
            "94": 22,  # Val-de-Marne
            "91": 40,  # Essonne
            "95": 30,  # Val-d'Oise
            "77": 45,  # Seine-et-Marne
            "78": 40,  # Yvelines
        }
        return dept_estimates.get(dept)

    # Known well-connected cities in Grande Couronne (have RER/Transilien even if not in listing)
    WELL_CONNECTED_CITIES_77_78 = {
        # 77 - Seine-et-Marne (RER A, RER E, Transilien)
        "chelles",
        "torcy",
        "lagny",
        "bussy-saint-georges",
        "bussy saint georges",
        "val d'europe",
        "marne-la-vallée",
        "marne la vallee",
        "chessy",
        "lognes",
        "noisiel",
        "noisy-le-grand",
        "noisy le grand",
        "pontault-combault",
        "roissy-en-brie",
        "ozoir-la-ferrière",
        "melun",
        "fontainebleau",
        "meaux",
        "villeparisis",
        # 78 - Yvelines (RER A, RER C, Transilien L/N/U)
        "versailles",
        "saint-germain-en-laye",
        "saint germain en laye",
        "poissy",
        "conflans-sainte-honorine",
        "conflans sainte honorine",
        "achères",
        "acheres",
        "maisons-laffitte",
        "maisons laffitte",
        "sartrouville",
        "houilles",
        "chatou",
        "le vésinet",
        "le vesinet",
        "rueil-malmaison",
        "nanterre",
        "la défense",
        "la defense",
        "saint-cloud",
        "sèvres",
        "sevres",
        "meudon",
        "clamart",
        "le chesnay",
        "vélizy",
        "velizy",
        "viroflay",
        "mantes-la-jolie",
        "les mureaux",
    }

    def _evaluate_location(
        self, listing: Listing, red_flags: list, green_flags: list
    ) -> CriterionScore:
        """Evaluate location and transport accessibility."""
        score = 70.0  # Base score
        details = []
        recommendations = []
        status = "✅"

        # City info
        city = listing.address.city
        postal = listing.address.postal_code
        details.append(f"{city} ({postal})")

        # Get commute time estimate
        commute_time = self.get_commute_time(city, postal)

        # Add commute time to details and check for red flag
        if commute_time is not None:
            details.append(f"~{commute_time}min to Paris")
            if commute_time > 35:
                score -= 15
                status = "⚠️"
                red_flags.append(f"Long commute ({commute_time}min to Paris)")
                recommendations.append(
                    f"Consider commute impact: ~{commute_time}min each way = {commute_time * 2}min/day"
                )
            elif commute_time <= 20:
                score += 5
                green_flags.append(f"Short commute (~{commute_time}min to Paris)")

        # Street info
        if listing.address.street:
            details.append(f"Street: {listing.address.street}")
        else:
            score -= 5
            recommendations.append("Visit the property to assess exact street location")

        # Determine zone (Paris connectivity)
        dept = postal[:2] if postal else ""
        has_metro = bool(listing.transport.metro_lines)
        has_rer = bool(listing.transport.rer_lines)
        has_transport = has_metro or has_rer

        # Metro/Transport access scoring
        transport_info = []
        if has_metro:
            lines = ", ".join(listing.transport.metro_lines)
            transport_info.append(f"Metro {lines}")
            score += 15

            if listing.transport.distance_to_transport:
                transport_info.append(f"({listing.transport.distance_to_transport})")
                green_flags.append(
                    f"Near Metro line(s) {lines} - {listing.transport.distance_to_transport}"
                )
            else:
                green_flags.append(f"Near Metro line(s) {lines}")
        elif has_rer:
            lines = ", ".join(listing.transport.rer_lines)
            transport_info.append(f"RER {lines}")
            score += 10

            if listing.transport.distance_to_transport:
                transport_info.append(f"({listing.transport.distance_to_transport})")
                green_flags.append(
                    f"Near RER line(s) {lines} - {listing.transport.distance_to_transport}"
                )
            else:
                green_flags.append(f"Near RER line(s) {lines}")
        else:
            score -= 10
            status = "⚠️"
            recommendations.append(
                "Verify public transport accessibility (Metro/RER within 10min walk)"
            )
            recommendations.append("Check distance to nearest station on Google Maps")

        if transport_info:
            details.append(" ".join(transport_info))

        # Paris proximity scoring by department
        if dept == "75":
            # Paris intra-muros
            score += 15
            green_flags.append("Located in Paris intra-muros")
            details.append("Paris - Excellent connectivity")
        elif dept in ("92", "93", "94"):
            # Petite Couronne - well connected
            score += 10
            green_flags.append("Petite Couronne - Good Paris access")
            details.append("Petite Couronne")
        elif dept in ("91", "95"):
            # Grande Couronne South/North - moderate
            if has_rer:
                score += 5
                details.append("Grande Couronne (RER connected)")
            else:
                score -= 10
                status = "⚠️"
                details.append("Grande Couronne - Limited transport")
                red_flags.append(f"Remote location ({city}) - No direct RER/Metro")
                recommendations.append(
                    "Check commute time to Paris (~45-60min+ likely)"
                )
        elif dept in ("77", "78"):
            # Grande Couronne East/West - check if known well-connected city
            city_lower = (city or "").lower()
            is_known_connected = any(
                known in city_lower for known in self.WELL_CONNECTED_CITIES_77_78
            )

            if has_rer or is_known_connected:
                score += 5  # Bonus for connected Grande Couronne
                details.append("Grande Couronne (RER/Transilien connected)")
                if is_known_connected and not has_rer:
                    green_flags.append(
                        f"{city} - Well connected to Paris via RER/Transilien"
                    )
            else:
                score -= 20
                status = "⚠️"
                details.append("Grande Couronne - Remote location")
                red_flags.append(f"Remote location ({city}) - Poor Paris connectivity")
                recommendations.append(
                    "⚠️ Likely 1h+ commute to Paris - verify transport options"
                )
                recommendations.append("Consider car dependency for this location")
        else:
            # Outside Île-de-France or unknown
            if not has_transport:
                score -= 15
                status = "⚠️"
                recommendations.append("Verify location and transport accessibility")

        return CriterionScore(
            name="Location & Transport",
            category="Location",
            score=min(max(score, 0), 100),  # Clamp between 0-100
            max_score=100,
            weight=self.WEIGHTS["location"],
            status=status,
            details=" | ".join(details),
            recommendations=recommendations,
        )

    def _evaluate_building(
        self, listing: Listing, red_flags: list, green_flags: list
    ) -> CriterionScore:
        """Evaluate building/copropriété health."""
        score = 70.0  # Base score
        details = []
        recommendations = []
        status = "✅"

        # Annual charges
        annual_charges = listing.price_info.annual_charges
        monthly_charges = listing.price_info.charges

        if annual_charges:
            monthly = annual_charges / 12
            details.append(f"Charges: {annual_charges:,}€/year ({monthly:.0f}€/month)")

            # Calculate charges per m²
            charges_per_m2_month = monthly / listing.surface_area

            if charges_per_m2_month > 4.5:  # > €4.50/m²/month is very high
                score -= 25
                status = "⚠️"
                red_flags.append(
                    f"Very high charges: {charges_per_m2_month:.1f}€/m²/month"
                )
                recommendations.append(
                    "Request breakdown of charges - may indicate expensive services or poor insulation"
                )
            elif charges_per_m2_month > 3.5:
                score -= 10
                recommendations.append(
                    "Charges are above average - verify what's included"
                )
            else:
                score += 10
                green_flags.append("Reasonable building charges")
        elif monthly_charges:
            details.append(f"Charges: {monthly_charges}€/month")
        else:
            score -= 5
            status = "❓"
            recommendations.append("Request 'appel de charges' for last 3 years")
            recommendations.append(
                "Ask about upcoming major works (ravalement, toiture)"
            )

        # Building lots (copropriété size)
        if listing.building.total_lots:
            lots = listing.building.total_lots
            details.append(f"Copropriété: {lots} lots")

            if lots < 10:
                score += 5
                details.append("(Small building - easier decisions)")
            elif lots > 50:
                score -= 5
                recommendations.append("Large copropriété - decisions can be slow")

        # Ongoing procedures
        if listing.building.has_ongoing_procedures is not None:
            if listing.building.has_ongoing_procedures:
                score -= 20
                status = "❌"
                red_flags.append("Legal procedures ongoing in the building!")
                recommendations.append(
                    "Get details on the nature of procedures before proceeding"
                )
            else:
                score += 10
                green_flags.append("No ongoing legal procedures in building")
                details.append("No procedures")
        else:
            recommendations.append(
                "Ask seller about any ongoing building disputes or procedures"
            )

        # Caretaker
        if listing.building.has_caretaker:
            score += 5
            green_flags.append("Building has a gardien/concierge")

        # Building era (affects maintenance needs)
        if listing.features.building_era:
            details.append(f"Era: {listing.features.building_era}")
            era = listing.features.building_era.lower()

            if "haussmann" in era:
                score += 5
                green_flags.append("Haussmannian building - typically well-maintained")
            elif any(x in era for x in ["60", "70"]):
                score -= 5
                recommendations.append(
                    "1960s-70s buildings often need facade/insulation work"
                )

        return CriterionScore(
            name="Building Health (Copropriété)",
            category="Building",
            score=max(score, 0),
            max_score=100,
            weight=self.WEIGHTS["building"],
            status=status,
            details=" | ".join(details),
            recommendations=recommendations,
        )

    def _evaluate_features(
        self, listing: Listing, red_flags: list, green_flags: list
    ) -> CriterionScore:
        """Evaluate intrinsic features (plus-value factors)."""
        score = 60.0  # Base score
        details = []
        recommendations = []
        status = "✅"

        # Floor level
        floor = listing.features.floor
        total_floors = listing.features.total_floors
        has_elevator = listing.features.has_elevator

        # Check for high-rise building (>10 floors)
        if total_floors is not None and total_floors > 10:
            score -= 15
            red_flags.append(
                f"High-rise building ({total_floors} floors) - less desirable, higher charges"
            )
            details.append(f"High-rise ({total_floors} floors) ⬇️")
            status = "⚠️"

        if floor is not None:
            if floor == 0:
                score -= 15
                red_flags.append(
                    "Ground floor (Rez-de-chaussée) - typically 15-25% less valuable"
                )
                details.append("RDC ⬇️")
            elif floor >= 4 and has_elevator:
                score += 10
                green_flags.append(
                    f"High floor ({floor}) with elevator - premium value"
                )
                details.append(f"Floor {floor} + elevator ⬆️")
            elif floor >= 4 and not has_elevator:
                score -= 5
                details.append(f"Floor {floor} without elevator")
                recommendations.append(
                    "High floor without elevator reduces resale pool"
                )
            else:
                details.append(f"Floor {floor}")

        # Orientation / Exposure
        exposure = listing.features.exposure
        orientation = listing.features.orientation

        if orientation:
            details.append(f"Orientation: {orientation}")
            if "south" in orientation.lower():
                score += 10
                green_flags.append("South-facing (excellent natural light)")

        if exposure:
            details.append(f"Exposure: {exposure}")
            if exposure.lower() in ["double", "triple", "traversant"]:
                score += 10
                green_flags.append(
                    f"{exposure} exposure - better light and ventilation"
                )

        # Luminosity
        if listing.features.luminosity:
            if "bright" in listing.features.luminosity.lower():
                score += 5
                details.append("Bright ☀️")

        # Condition
        condition = listing.features.condition
        if condition:
            details.append(f"Condition: {condition}")
            if "no work" in condition.lower() or "excellent" in condition.lower():
                score += 10
                green_flags.append("No renovation work needed")
            elif "renovate" in condition.lower() or "refresh" in condition.lower():
                score -= 10
                recommendations.append("Budget for renovation costs")

        # Premium features
        premium_features = []
        if listing.features.has_terrace:
            premium_features.append("terrace")
            score += 10
        if listing.features.has_balcony:
            premium_features.append("balcony")
            score += 5
        if listing.features.has_parking:
            premium_features.append("parking")
            score += 10
        if listing.features.has_garden:
            premium_features.append("garden")
            score += 10
        if listing.features.has_cellar:
            premium_features.append("cellar")
            score += 3

        if premium_features:
            details.append(f"Plus: {', '.join(premium_features)}")
            green_flags.append(f"Premium features: {', '.join(premium_features)}")

        # Interior quality
        quality_features = []
        if listing.features.has_parquet:
            quality_features.append("parquet")
        if listing.features.has_fireplace:
            quality_features.append("fireplace")
        if listing.features.has_high_ceilings:
            quality_features.append("high ceilings")
        if listing.features.has_moldings:
            quality_features.append("moldings")

        if quality_features:
            score += min(len(quality_features) * 3, 12)
            details.append(f"Character: {', '.join(quality_features)}")

        return CriterionScore(
            name="Intrinsic Features",
            category="Features",
            score=min(score, 100),
            max_score=100,
            weight=self.WEIGHTS["features"],
            status=status,
            details=" | ".join(details),
            recommendations=recommendations,
        )

    def _score_to_rating(self, score: float) -> Rating:
        """Convert numeric score to rating."""
        if score >= 90:
            return Rating.EXCELLENT
        elif score >= 75:
            return Rating.GOOD
        elif score >= 60:
            return Rating.AVERAGE
        elif score >= 40:
            return Rating.BELOW_AVG
        else:
            return Rating.POOR

    def _determine_risk(self, listing: Listing, red_flags: list) -> RiskLevel:
        """Determine investment risk level."""
        # Critical risks
        dpe = listing.energy_rating.energy_class
        if dpe == EnergyClass.G:
            return RiskLevel.CRITICAL
        if listing.building.has_ongoing_procedures:
            return RiskLevel.CRITICAL

        # High risks
        if dpe in [EnergyClass.F, EnergyClass.E]:
            return RiskLevel.HIGH
        if len(red_flags) >= 3:
            return RiskLevel.HIGH

        # Medium risks
        if len(red_flags) >= 1:
            return RiskLevel.MEDIUM
        if dpe == EnergyClass.UNKNOWN:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def _estimate_fair_value(self, listing: Listing) -> Optional[float]:
        """Estimate fair market value using formula."""
        dept = listing.address.postal_code[:2]
        avg_price = self.AVG_PRICES_PER_M2.get(dept, self.AVG_PRICES_PER_M2["default"])

        # Use Carrez surface if available, otherwise advertised
        surface = listing.carrez_area or listing.surface_area

        # Base value
        base_value = surface * avg_price

        # Adjustments
        adjustments = 1.0

        # DPE adjustment
        dpe = listing.energy_rating.energy_class
        if dpe == EnergyClass.G:
            adjustments -= 0.15
        elif dpe == EnergyClass.F:
            adjustments -= 0.10
        elif dpe == EnergyClass.E:
            adjustments -= 0.05
        elif dpe in [EnergyClass.A, EnergyClass.B]:
            adjustments += 0.05

        # Floor adjustment
        if listing.features.floor == 0:
            adjustments -= 0.15
        elif (
            listing.features.floor
            and listing.features.floor >= 4
            and listing.features.has_elevator
        ):
            adjustments += 0.05

        # Premium features
        if listing.features.has_terrace:
            adjustments += 0.08
        if listing.features.has_parking:
            adjustments += 0.05

        return base_value * adjustments

    def _calculate_negotiation_margin(
        self,
        listing: Listing,
        energy_score: CriterionScore,
        building_score: CriterionScore,
    ) -> Optional[float]:
        """Calculate suggested negotiation margin."""
        margin = 0.0

        # DPE-based negotiation
        dpe = listing.energy_rating.energy_class
        if dpe == EnergyClass.G:
            margin += 15
        elif dpe == EnergyClass.F:
            margin += 12
        elif dpe == EnergyClass.E:
            margin += 8

        # Building issues
        if listing.building.has_ongoing_procedures:
            margin += 10

        # High charges
        if listing.price_info.annual_charges:
            monthly = listing.price_info.annual_charges / 12 / listing.surface_area
            if monthly > 4.5:
                margin += 5

        return margin if margin > 0 else None

    def _generate_summary(
        self, listing: Listing, score: float, red_flags: list, green_flags: list
    ) -> str:
        """Generate evaluation summary."""
        parts = []

        # Overall assessment
        if score >= 80:
            parts.append(
                "This listing shows strong fundamentals and presents a good investment opportunity."
            )
        elif score >= 60:
            parts.append(
                "This listing has average characteristics with some points requiring attention."
            )
        else:
            parts.append(
                "This listing presents significant risks that warrant careful consideration."
            )

        # Key points
        if green_flags:
            parts.append(f"Key strengths: {', '.join(green_flags[:3])}.")

        if red_flags:
            parts.append(f"Main concerns: {', '.join(red_flags[:3])}.")

        # Final recommendation
        dpe = listing.energy_rating.energy_class
        if dpe == EnergyClass.G:
            parts.append(
                "⚠️ CRITICAL: This property cannot be legally rented. Only suitable for personal use or with major renovation budget."
            )
        elif dpe in [EnergyClass.F, EnergyClass.E]:
            parts.append(
                "Consider the cost of energy renovation before purchasing. Negotiate accordingly."
            )

        return " ".join(parts)
