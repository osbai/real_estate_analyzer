"""Notary fees (Frais de Notaire) calculator for French real estate.

In France, notary fees vary significantly based on property type:
- Ancien (old build, >5 years): ~7-8% of purchase price
- VEFA/Neuf (new build, <5 years): ~2-3% of purchase price

These fees are a major hidden cost that investors must account for.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import re


class PropertyBuildType(str, Enum):
    """Type of property build affecting notary fees."""
    
    ANCIEN = "ancien"  # Old build (>5 years) - ~7-8% fees
    NEUF = "neuf"  # New build (<5 years, VEFA) - ~2-3% fees
    UNKNOWN = "unknown"  # Default to ancien rates


@dataclass
class NotaryFeesBreakdown:
    """Detailed breakdown of notary fees."""
    
    purchase_price: int
    property_type: PropertyBuildType
    
    # Fee components
    droits_mutation: int  # Transfer taxes (droits de mutation)
    emoluments_notaire: int  # Notary's regulated fees
    debours: int  # Disbursements (administrative costs)
    contribution_securite: int  # Security contribution
    
    # Totals
    total_fees: int
    fee_percentage: float
    total_acquisition_cost: int
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "purchase_price": self.purchase_price,
            "property_type": self.property_type.value,
            "droits_mutation": self.droits_mutation,
            "emoluments_notaire": self.emoluments_notaire,
            "debours": self.debours,
            "contribution_securite": self.contribution_securite,
            "total_fees": self.total_fees,
            "fee_percentage": round(self.fee_percentage, 2),
            "total_acquisition_cost": self.total_acquisition_cost,
        }


class NotaryFeesCalculator:
    """Calculator for French notary fees (Frais de Notaire).
    
    The calculator uses the official French fee structure:
    
    1. Droits de mutation (Transfer taxes):
       - Ancien: ~5.80% (varies slightly by department)
       - Neuf: ~0.71% (TVA already paid)
    
    2. Émoluments du notaire (Notary's regulated fees):
       - Sliding scale based on property price
       - Same for ancien and neuf
    
    3. Débours (Disbursements):
       - Administrative costs, ~1000-1500€
    
    4. Contribution de sécurité immobilière:
       - 0.10% of property price
    """
    
    # Transfer tax rates by property type
    DROITS_MUTATION_ANCIEN = 0.0580  # 5.80% for old properties
    DROITS_MUTATION_NEUF = 0.0071  # 0.71% for new properties
    
    # Notary's emoluments - sliding scale (2024 rates)
    # Each bracket: (threshold, rate, previous bracket total)
    EMOLUMENTS_BRACKETS = [
        (6500, 0.03870, 0),  # 0-6500€: 3.870%
        (17000, 0.01596, 251.55),  # 6500-17000€: 1.596%
        (60000, 0.01064, 419.12),  # 17000-60000€: 1.064%
        (float("inf"), 0.00799, 876.64),  # >60000€: 0.799%
    ]
    
    # Fixed costs
    CONTRIBUTION_SECURITE_RATE = 0.001  # 0.10%
    DEBOURS_BASE = 1200  # Average disbursements
    
    # Keywords to detect new builds
    NEUF_KEYWORDS = [
        "vefa", "neuf", "livraison", "programme neuf", "résidence neuve",
        "immeuble neuf", "frais de notaire réduits", "frais réduits",
        "construction neuve", "première main", "jamais habité",
        "achèvement", "état futur", "sur plan"
    ]
    
    def detect_property_type(
        self, 
        description: Optional[str] = None,
        title: Optional[str] = None,
        year_built: Optional[int] = None,
        condition: Optional[str] = None
    ) -> PropertyBuildType:
        """Detect if property is new or old build based on listing data.
        
        Args:
            description: Listing description text
            title: Listing title
            year_built: Year property was built
            condition: Property condition (e.g., "neuf", "rénové")
        
        Returns:
            PropertyBuildType indicating ancien or neuf
        """
        # Check year built (properties < 5 years old are considered "neuf")
        if year_built:
            from datetime import datetime
            current_year = datetime.now().year
            if current_year - year_built < 5:
                return PropertyBuildType.NEUF
        
        # Check condition field
        if condition:
            condition_lower = condition.lower()
            if "neuf" in condition_lower and "rénové" not in condition_lower:
                return PropertyBuildType.NEUF
        
        # Search for keywords in description and title
        text_to_search = ""
        if description:
            text_to_search += description.lower()
        if title:
            text_to_search += " " + title.lower()
        
        for keyword in self.NEUF_KEYWORDS:
            if keyword in text_to_search:
                return PropertyBuildType.NEUF
        
        # Default to ancien (most common case)
        return PropertyBuildType.ANCIEN
    
    def calculate_emoluments(self, price: int) -> int:
        """Calculate notary's emoluments using sliding scale.
        
        Args:
            price: Property purchase price in euros
            
        Returns:
            Notary's emoluments in euros
        """
        emoluments = 0.0
        previous_threshold = 0
        
        for threshold, rate, bracket_base in self.EMOLUMENTS_BRACKETS:
            if price <= threshold:
                # Within this bracket
                emoluments = bracket_base + (price - previous_threshold) * rate
                break
            previous_threshold = threshold
        
        # Apply TVA (20%) to notary fees
        emoluments *= 1.20
        
        return int(emoluments)
    
    def calculate(
        self, 
        price: int, 
        property_type: Optional[PropertyBuildType] = None,
        description: Optional[str] = None,
        title: Optional[str] = None,
        year_built: Optional[int] = None,
        condition: Optional[str] = None
    ) -> NotaryFeesBreakdown:
        """Calculate complete notary fees breakdown.
        
        Args:
            price: Property purchase price in euros
            property_type: Explicitly set property type (ancien/neuf)
            description: Listing description for auto-detection
            title: Listing title for auto-detection
            year_built: Year built for auto-detection
            condition: Property condition for auto-detection
            
        Returns:
            NotaryFeesBreakdown with detailed fee components
        """
        # Determine property type
        if property_type is None:
            property_type = self.detect_property_type(
                description=description,
                title=title,
                year_built=year_built,
                condition=condition
            )
        
        # Calculate transfer taxes
        if property_type == PropertyBuildType.NEUF:
            droits_mutation = int(price * self.DROITS_MUTATION_NEUF)
        else:
            droits_mutation = int(price * self.DROITS_MUTATION_ANCIEN)
        
        # Calculate notary emoluments
        emoluments_notaire = self.calculate_emoluments(price)
        
        # Fixed costs
        debours = self.DEBOURS_BASE
        contribution_securite = int(price * self.CONTRIBUTION_SECURITE_RATE)
        
        # Total fees
        total_fees = droits_mutation + emoluments_notaire + debours + contribution_securite
        fee_percentage = (total_fees / price) * 100
        total_acquisition_cost = price + total_fees
        
        return NotaryFeesBreakdown(
            purchase_price=price,
            property_type=property_type,
            droits_mutation=droits_mutation,
            emoluments_notaire=emoluments_notaire,
            debours=debours,
            contribution_securite=contribution_securite,
            total_fees=total_fees,
            fee_percentage=fee_percentage,
            total_acquisition_cost=total_acquisition_cost,
        )
    
    def quick_estimate(self, price: int, is_neuf: bool = False) -> tuple[int, float]:
        """Quick estimate of notary fees without detailed breakdown.
        
        Args:
            price: Property purchase price in euros
            is_neuf: True for new build, False for old
            
        Returns:
            Tuple of (total_fees, percentage)
        """
        if is_neuf:
            rate = 0.025  # ~2.5% for new builds
        else:
            rate = 0.075  # ~7.5% for old builds
        
        fees = int(price * rate)
        return fees, rate * 100
    
    def format_breakdown(self, breakdown: NotaryFeesBreakdown) -> str:
        """Format fees breakdown as readable text."""
        lines = [
            "📝 FRAIS DE NOTAIRE (Notary Fees)",
            "─" * 40,
            f"Property type: {breakdown.property_type.value.upper()}",
            f"Purchase price: {breakdown.purchase_price:,}€",
            "",
            "Fee breakdown:",
            f"  • Droits de mutation: {breakdown.droits_mutation:,}€",
            f"  • Émoluments notaire: {breakdown.emoluments_notaire:,}€",
            f"  • Débours: {breakdown.debours:,}€",
            f"  • Contribution sécurité: {breakdown.contribution_securite:,}€",
            "─" * 40,
            f"TOTAL FEES: {breakdown.total_fees:,}€ ({breakdown.fee_percentage:.1f}%)",
            f"TOTAL ACQUISITION: {breakdown.total_acquisition_cost:,}€",
        ]
        return "\n".join(lines)
