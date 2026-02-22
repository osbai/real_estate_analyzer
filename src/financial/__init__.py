"""Financial analysis module for French real estate investment.

This module provides tools for:
- Yield calculation (gross and net)
- Notary fees calculation (frais de notaire)
- Cash flow modeling and loan simulation
- Investment analysis and profitability assessment
"""

from .notary_fees import NotaryFeesCalculator, PropertyBuildType
from .yield_calculator import YieldCalculator, YieldAnalysis
from .cashflow import CashFlowModeler, LoanParameters, CashFlowAnalysis
from .investment import InvestmentAnalyzer, InvestmentReport

__all__ = [
    # Notary fees
    "NotaryFeesCalculator",
    "PropertyBuildType",
    # Yield
    "YieldCalculator",
    "YieldAnalysis",
    # Cash flow
    "CashFlowModeler",
    "LoanParameters",
    "CashFlowAnalysis",
    # Investment
    "InvestmentAnalyzer",
    "InvestmentReport",
]
