"""Cash flow modeler for French real estate investment.

This module simulates loan scenarios and calculates monthly cash flow
to determine if a property investment will be:
- Cash Flow Positive: Rental income covers all costs
- Effort d'épargne: Monthly out-of-pocket payment required

Features:
- Loan amortization calculation (French fixed-rate mortgages)
- Multiple scenario comparison (15/20/25 year terms)
- Break-even analysis
- Sensitivity testing
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CashFlowStatus(str, Enum):
    """Status of monthly cash flow."""

    POSITIVE = "🟢 Cash Flow Positive"
    NEUTRAL = "🟡 Break-even"
    NEGATIVE = "🔴 Effort d'épargne"


@dataclass
class LoanParameters:
    """Parameters for loan simulation."""

    loan_amount: int  # Principal (price - down payment)
    interest_rate: float  # Annual rate as percentage (e.g., 3.5 for 3.5%)
    duration_years: int  # Loan term in years
    insurance_rate: float = 0.30  # Annual insurance as % of loan (typical: 0.25-0.40%)

    @property
    def monthly_rate(self) -> float:
        """Monthly interest rate as decimal."""
        return (self.interest_rate / 100) / 12

    @property
    def num_payments(self) -> int:
        """Total number of monthly payments."""
        return self.duration_years * 12

    @property
    def monthly_insurance(self) -> float:
        """Monthly insurance cost."""
        return (self.loan_amount * self.insurance_rate / 100) / 12


@dataclass
class CashFlowAnalysis:
    """Complete cash flow analysis for a rental property."""

    # Investment details
    purchase_price: int
    down_payment: int
    down_payment_percentage: float
    loan_amount: int
    notary_fees: int
    total_investment: int  # Down payment + notary fees

    # Loan details
    loan_duration_years: int
    interest_rate: float
    monthly_mortgage: float  # Principal + Interest
    monthly_insurance: float  # Loan insurance (assurance emprunteur)
    total_monthly_loan_cost: float  # Mortgage + Insurance

    # Monthly income/expenses
    monthly_rent: float
    monthly_charges: float  # Non-recoverable copropriété charges
    monthly_property_tax: float  # Taxe foncière / 12
    monthly_pno_insurance: float  # Propriétaire Non Occupant
    monthly_management_fees: float  # If using property manager

    # Cash flow
    monthly_income: float
    monthly_expenses: float
    monthly_cash_flow: float
    cash_flow_status: CashFlowStatus

    # Annual summary
    annual_cash_flow: float
    cash_on_cash_return: float  # Annual cash flow / Initial investment

    # Break-even
    break_even_rent: float  # Rent needed for neutral cash flow
    rent_coverage_ratio: float  # Actual rent / Break-even rent

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "purchase_price": self.purchase_price,
            "down_payment": self.down_payment,
            "down_payment_percentage": round(self.down_payment_percentage, 1),
            "loan_amount": self.loan_amount,
            "notary_fees": self.notary_fees,
            "total_investment": self.total_investment,
            "loan_duration_years": self.loan_duration_years,
            "interest_rate": self.interest_rate,
            "monthly_mortgage": round(self.monthly_mortgage, 2),
            "monthly_insurance": round(self.monthly_insurance, 2),
            "total_monthly_loan_cost": round(self.total_monthly_loan_cost, 2),
            "monthly_rent": self.monthly_rent,
            "monthly_charges": round(self.monthly_charges, 2),
            "monthly_property_tax": round(self.monthly_property_tax, 2),
            "monthly_pno_insurance": round(self.monthly_pno_insurance, 2),
            "monthly_management_fees": round(self.monthly_management_fees, 2),
            "monthly_income": round(self.monthly_income, 2),
            "monthly_expenses": round(self.monthly_expenses, 2),
            "monthly_cash_flow": round(self.monthly_cash_flow, 2),
            "cash_flow_status": self.cash_flow_status.value,
            "annual_cash_flow": round(self.annual_cash_flow, 2),
            "cash_on_cash_return": round(self.cash_on_cash_return, 2),
            "break_even_rent": round(self.break_even_rent, 2),
            "rent_coverage_ratio": round(self.rent_coverage_ratio, 2),
        }


@dataclass
class LoanComparison:
    """Comparison of multiple loan scenarios."""

    scenarios: list[CashFlowAnalysis]
    best_cash_flow: Optional[CashFlowAnalysis] = None
    lowest_monthly_payment: Optional[CashFlowAnalysis] = None
    recommendation: str = ""


class CashFlowModeler:
    """Cash flow calculator for rental property investments.

    This class models the financial performance of a rental property
    under different loan scenarios to help investors understand:

    1. Monthly cash flow (income - all expenses)
    2. Whether property will require monthly "effort d'épargne"
    3. Break-even rent needed to cover all costs
    4. Optimal loan structure for their situation

    French-specific considerations:
    - Assurance emprunteur (loan insurance) is mandatory
    - Interest rates are typically fixed for the entire term
    - Maximum debt-to-income ratio is 35% (Haut Conseil de Stabilité Financière)
    """

    # Current market rates (2024)
    DEFAULT_RATES = {
        15: 3.45,  # 15-year rate
        20: 3.55,  # 20-year rate
        25: 3.65,  # 25-year rate
    }

    # Default assumptions
    DEFAULT_DOWN_PAYMENT_RATE = 0.20  # 20% down
    DEFAULT_INSURANCE_RATE = 0.30  # 0.30% annually
    DEFAULT_MANAGEMENT_FEE_RATE = 0.07  # 7% of rent
    DEFAULT_PNO_INSURANCE_RATE = 0.002  # 0.2% of property value
    DEFAULT_NON_RECOVERABLE_CHARGES_RATE = 0.30  # ~30% of charges non-recoverable

    def calculate_monthly_payment(self, loan_params: LoanParameters) -> float:
        """Calculate monthly mortgage payment (principal + interest).

        Uses the standard amortization formula:
        M = P * [r(1+r)^n] / [(1+r)^n - 1]

        Where:
        - M = Monthly payment
        - P = Principal (loan amount)
        - r = Monthly interest rate
        - n = Number of payments

        Args:
            loan_params: Loan parameters

        Returns:
            Monthly payment amount in euros
        """
        P = loan_params.loan_amount
        r = loan_params.monthly_rate
        n = loan_params.num_payments

        if r == 0:
            # Edge case: 0% interest rate
            return P / n

        monthly_payment = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
        return monthly_payment

    def calculate_total_loan_cost(self, loan_params: LoanParameters) -> dict:
        """Calculate total cost of loan over its lifetime.

        Args:
            loan_params: Loan parameters

        Returns:
            Dictionary with cost breakdown
        """
        monthly_payment = self.calculate_monthly_payment(loan_params)
        total_payments = monthly_payment * loan_params.num_payments
        total_interest = total_payments - loan_params.loan_amount
        total_insurance = loan_params.monthly_insurance * loan_params.num_payments

        return {
            "monthly_payment": monthly_payment,
            "total_payments": total_payments,
            "total_interest": total_interest,
            "total_insurance": total_insurance,
            "total_cost": total_payments + total_insurance,
        }

    def calculate(
        self,
        purchase_price: int,
        monthly_rent: float,
        down_payment_percentage: float = 20.0,
        interest_rate: Optional[float] = None,
        duration_years: int = 20,
        insurance_rate: float = 0.30,
        notary_fees: Optional[int] = None,
        annual_charges: Optional[int] = None,
        annual_property_tax: Optional[int] = None,
        surface_area: Optional[float] = None,
        use_management_company: bool = False,
        is_neuf: bool = False,
    ) -> CashFlowAnalysis:
        """Calculate complete cash flow analysis.

        Args:
            purchase_price: Property purchase price
            monthly_rent: Expected monthly rental income
            down_payment_percentage: Down payment as % of price (default: 20%)
            interest_rate: Annual rate (default: market rate for duration)
            duration_years: Loan term (default: 20)
            insurance_rate: Annual loan insurance rate (default: 0.30%)
            notary_fees: Total notary fees (estimated if not provided)
            annual_charges: Annual copropriété charges
            annual_property_tax: Annual taxe foncière
            surface_area: Property surface for expense estimation
            use_management_company: Whether using property manager
            is_neuf: Whether property is new (affects notary fees)

        Returns:
            Complete CashFlowAnalysis object
        """
        # Calculate down payment and loan amount
        down_payment = int(purchase_price * (down_payment_percentage / 100))
        loan_amount = purchase_price - down_payment

        # Get interest rate (use default if not provided)
        if interest_rate is None:
            interest_rate = self.DEFAULT_RATES.get(duration_years, 3.55)

        # Estimate notary fees if not provided
        if notary_fees is None:
            if is_neuf:
                notary_fees = int(purchase_price * 0.025)  # ~2.5% for new
            else:
                notary_fees = int(purchase_price * 0.075)  # ~7.5% for old

        # Total initial investment (what you pay out of pocket)
        total_investment = down_payment + notary_fees

        # Create loan parameters
        loan_params = LoanParameters(
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            duration_years=duration_years,
            insurance_rate=insurance_rate,
        )

        # Calculate mortgage payment
        monthly_mortgage = self.calculate_monthly_payment(loan_params)
        monthly_insurance = loan_params.monthly_insurance
        total_monthly_loan_cost = monthly_mortgage + monthly_insurance

        # Estimate monthly expenses
        # Charges (estimate ~30% non-recoverable from tenant)
        if annual_charges is not None:
            monthly_charges = (
                annual_charges * self.DEFAULT_NON_RECOVERABLE_CHARGES_RATE
            ) / 12
        elif surface_area:
            # Estimate at ~€3/m²/month, 30% non-recoverable
            monthly_charges = (
                surface_area * 3 * self.DEFAULT_NON_RECOVERABLE_CHARGES_RATE
            )
        else:
            monthly_charges = 100  # Default estimate

        # Property tax
        if annual_property_tax is not None:
            monthly_property_tax = annual_property_tax / 12
        else:
            # Estimate at ~1.5 months rent equivalent
            monthly_property_tax = monthly_rent * 1.5 / 12

        # PNO insurance
        monthly_pno_insurance = (purchase_price * self.DEFAULT_PNO_INSURANCE_RATE) / 12

        # Management fees
        if use_management_company:
            monthly_management_fees = monthly_rent * self.DEFAULT_MANAGEMENT_FEE_RATE
        else:
            monthly_management_fees = 0

        # Calculate cash flow
        monthly_income = monthly_rent
        monthly_expenses = (
            total_monthly_loan_cost
            + monthly_charges
            + monthly_property_tax
            + monthly_pno_insurance
            + monthly_management_fees
        )
        monthly_cash_flow = monthly_income - monthly_expenses

        # Determine status
        if monthly_cash_flow > 50:  # Small buffer for rounding
            cash_flow_status = CashFlowStatus.POSITIVE
        elif monthly_cash_flow >= -50:
            cash_flow_status = CashFlowStatus.NEUTRAL
        else:
            cash_flow_status = CashFlowStatus.NEGATIVE

        # Annual figures
        annual_cash_flow = monthly_cash_flow * 12

        # Cash-on-cash return (annual cash flow / initial investment)
        if total_investment > 0:
            cash_on_cash_return = (annual_cash_flow / total_investment) * 100
        else:
            cash_on_cash_return = 0

        # Break-even rent calculation
        expenses_without_income = (
            total_monthly_loan_cost
            + monthly_charges
            + monthly_property_tax
            + monthly_pno_insurance
        )
        if use_management_company:
            # Management fee is proportional to rent
            # break_even_rent = expenses / (1 - management_rate)
            break_even_rent = expenses_without_income / (
                1 - self.DEFAULT_MANAGEMENT_FEE_RATE
            )
        else:
            break_even_rent = expenses_without_income

        # Rent coverage ratio
        rent_coverage_ratio = (
            monthly_rent / break_even_rent if break_even_rent > 0 else 0
        )

        return CashFlowAnalysis(
            purchase_price=purchase_price,
            down_payment=down_payment,
            down_payment_percentage=down_payment_percentage,
            loan_amount=loan_amount,
            notary_fees=notary_fees,
            total_investment=total_investment,
            loan_duration_years=duration_years,
            interest_rate=interest_rate,
            monthly_mortgage=monthly_mortgage,
            monthly_insurance=monthly_insurance,
            total_monthly_loan_cost=total_monthly_loan_cost,
            monthly_rent=monthly_rent,
            monthly_charges=monthly_charges,
            monthly_property_tax=monthly_property_tax,
            monthly_pno_insurance=monthly_pno_insurance,
            monthly_management_fees=monthly_management_fees,
            monthly_income=monthly_income,
            monthly_expenses=monthly_expenses,
            monthly_cash_flow=monthly_cash_flow,
            cash_flow_status=cash_flow_status,
            annual_cash_flow=annual_cash_flow,
            cash_on_cash_return=cash_on_cash_return,
            break_even_rent=break_even_rent,
            rent_coverage_ratio=rent_coverage_ratio,
        )

    def compare_scenarios(
        self,
        purchase_price: int,
        monthly_rent: float,
        durations: list[int] = [15, 20, 25],
        down_payment_percentages: list[float] = [10, 20, 30],
        **kwargs,
    ) -> LoanComparison:
        """Compare multiple loan scenarios.

        Args:
            purchase_price: Property purchase price
            monthly_rent: Expected monthly rental income
            durations: List of loan durations to compare
            down_payment_percentages: List of down payment percentages
            **kwargs: Additional parameters passed to calculate()

        Returns:
            LoanComparison with all scenarios and recommendations
        """
        scenarios = []

        for duration in durations:
            for dp_pct in down_payment_percentages:
                analysis = self.calculate(
                    purchase_price=purchase_price,
                    monthly_rent=monthly_rent,
                    down_payment_percentage=dp_pct,
                    duration_years=duration,
                    **kwargs,
                )
                scenarios.append(analysis)

        # Find best scenarios
        positive_scenarios = [s for s in scenarios if s.monthly_cash_flow > 0]

        if positive_scenarios:
            best_cash_flow = max(positive_scenarios, key=lambda s: s.monthly_cash_flow)
        else:
            best_cash_flow = max(scenarios, key=lambda s: s.monthly_cash_flow)

        lowest_monthly = min(scenarios, key=lambda s: s.total_monthly_loan_cost)

        # Generate recommendation
        if positive_scenarios:
            recommendation = (
                f"✅ {len(positive_scenarios)} scenario(s) achieve positive cash flow. "
                f"Best: {best_cash_flow.duration_years}yr loan with "
                f"{best_cash_flow.down_payment_percentage:.0f}% down "
                f"(+{best_cash_flow.monthly_cash_flow:.0f}€/month)."
            )
        else:
            min_loss = min(abs(s.monthly_cash_flow) for s in scenarios)
            recommendation = (
                f"⚠️ No scenario achieves positive cash flow. "
                f"Minimum effort d'épargne: {min_loss:.0f}€/month. "
                f"Consider: higher rent, larger down payment, or different property."
            )

        return LoanComparison(
            scenarios=scenarios,
            best_cash_flow=best_cash_flow,
            lowest_monthly_payment=lowest_monthly,
            recommendation=recommendation,
        )

    def format_analysis(self, analysis: CashFlowAnalysis) -> str:
        """Format cash flow analysis as readable text."""
        lines = [
            "💰 CASH FLOW ANALYSIS (Analyse de Cash-Flow)",
            "═" * 55,
            "",
            "FINANCING STRUCTURE",
            "─" * 55,
            f"Purchase price: {analysis.purchase_price:,}€",
            f"Down payment: {analysis.down_payment:,}€ ({analysis.down_payment_percentage:.0f}%)",
            f"Loan amount: {analysis.loan_amount:,}€",
            f"Notary fees: {analysis.notary_fees:,}€",
            f"Total out-of-pocket: {analysis.total_investment:,}€",
            "",
            "LOAN DETAILS",
            "─" * 55,
            f"Duration: {analysis.loan_duration_years} years",
            f"Interest rate: {analysis.interest_rate:.2f}%",
            f"Monthly mortgage (P+I): {analysis.monthly_mortgage:,.0f}€",
            f"Monthly insurance: {analysis.monthly_insurance:,.0f}€",
            f"Total monthly loan cost: {analysis.total_monthly_loan_cost:,.0f}€",
            "",
            "MONTHLY CASH FLOW",
            "═" * 55,
            f"  Rental income: +{analysis.monthly_income:,.0f}€",
            "  ─────────────────────────────",
            f"  Mortgage payment: -{analysis.monthly_mortgage:,.0f}€",
            f"  Loan insurance: -{analysis.monthly_insurance:,.0f}€",
            f"  Copro charges: -{analysis.monthly_charges:,.0f}€",
            f"  Property tax: -{analysis.monthly_property_tax:,.0f}€",
            f"  PNO insurance: -{analysis.monthly_pno_insurance:,.0f}€",
        ]

        if analysis.monthly_management_fees > 0:
            lines.append(
                f"  Management fees: -{analysis.monthly_management_fees:,.0f}€"
            )

        lines.extend(
            [
                "  ═════════════════════════════",
                f"  NET CASH FLOW: {'+' if analysis.monthly_cash_flow >= 0 else ''}{analysis.monthly_cash_flow:,.0f}€/month",
                "",
                f"STATUS: {analysis.cash_flow_status.value}",
                "",
                "KEY METRICS",
                "─" * 55,
                f"Annual cash flow: {'+' if analysis.annual_cash_flow >= 0 else ''}{analysis.annual_cash_flow:,.0f}€",
                f"Cash-on-cash return: {analysis.cash_on_cash_return:.2f}%",
                f"Break-even rent: {analysis.break_even_rent:,.0f}€/month",
                f"Rent coverage ratio: {analysis.rent_coverage_ratio:.2f}x",
                "═" * 55,
            ]
        )

        return "\n".join(lines)

    def format_comparison(self, comparison: LoanComparison) -> str:
        """Format loan comparison as readable text."""
        lines = [
            "📊 LOAN SCENARIO COMPARISON",
            "═" * 80,
            "",
            f"{'Duration':<10} {'Down Pmt':<12} {'Monthly Pmt':<14} {'Cash Flow':<14} {'Status':<20}",
            "─" * 80,
        ]

        for s in sorted(comparison.scenarios, key=lambda x: (-x.monthly_cash_flow)):
            status_short = {
                CashFlowStatus.POSITIVE: "🟢 Positive",
                CashFlowStatus.NEUTRAL: "🟡 Neutral",
                CashFlowStatus.NEGATIVE: "🔴 Negative",
            }[s.cash_flow_status]

            cf_str = (
                f"{'+' if s.monthly_cash_flow >= 0 else ''}{s.monthly_cash_flow:,.0f}€"
            )

            lines.append(
                f"{s.loan_duration_years:>2} years    "
                f"{s.down_payment_percentage:>3.0f}% ({s.down_payment:>6,}€)  "
                f"{s.total_monthly_loan_cost:>8,.0f}€      "
                f"{cf_str:>10}      "
                f"{status_short}"
            )

        lines.extend(
            [
                "─" * 80,
                "",
                f"💡 {comparison.recommendation}",
                "",
                "═" * 80,
            ]
        )

        return "\n".join(lines)
