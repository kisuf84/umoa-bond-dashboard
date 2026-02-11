"""
UMOA Yield Calculator
Calculate yield for UMOA bonds following market conventions:
- BAT (Bons du Trésor): Simple yield with ACT/360 convention
- OAT (Obligations Assimilables du Trésor): Yield to Maturity using DIRTY PRICE
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional, List, Tuple
import math


class UMOAYieldCalculator:
    """Calculate yields for UMOA bonds"""

    @staticmethod
    def calculate_bat_yield(
        price: float,
        settlement_date: date,
        maturity_date: date,
        nominal_value: float = 100.0
    ) -> Optional[float]:
        """
        Calculate BAT (Bons du Trésor) yield using simple yield formula.

        BAT are money market instruments (zero-coupon).
        Convention: ACT/360 (Actual days / 360)

        Formula: Yield = ((Nominal / Price) - 1) × (360 / Days_to_Maturity) × 100
        """
        try:
            days_to_maturity = (maturity_date - settlement_date).days
            if days_to_maturity <= 0:
                return None

            if price <= 0:
                return None

            # Simple yield formula: ((Nominal/Price) - 1) × (360/Days)
            yield_rate = ((nominal_value / price) - 1) * (360.0 / days_to_maturity) * 100

            return round(yield_rate, 4)

        except Exception as e:
            print(f"BAT yield calculation error: {e}")
            return None

    @staticmethod
    def get_coupon_dates(settlement_date: date, maturity_date: date, frequency: int = 1) -> List[date]:
        """
        Get all remaining coupon dates from settlement to maturity.
        Coupon dates are based on maturity date anniversary.
        """
        coupon_dates = []
        period_months = 12 // frequency

        # Start from maturity and work backwards to find coupon dates
        current = maturity_date
        while current > settlement_date:
            coupon_dates.append(current)
            # Go back by period
            year = current.year
            month = current.month - period_months
            day = current.day

            while month <= 0:
                month += 12
                year -= 1

            # Handle day overflow (e.g., Feb 30 -> Feb 28)
            while True:
                try:
                    current = date(year, month, day)
                    break
                except ValueError:
                    day -= 1

        coupon_dates.reverse()
        return coupon_dates

    @staticmethod
    def get_previous_coupon_date(settlement_date: date, maturity_date: date, frequency: int = 1) -> date:
        """
        Get the coupon date immediately before settlement date.
        """
        period_months = 12 // frequency

        # Start from maturity and work backwards
        current = maturity_date
        previous = None

        while current > settlement_date:
            previous = current
            # Go back by period
            year = current.year
            month = current.month - period_months
            day = current.day

            while month <= 0:
                month += 12
                year -= 1

            # Handle day overflow
            while True:
                try:
                    current = date(year, month, day)
                    break
                except ValueError:
                    day -= 1

        # 'current' is now the previous coupon date (before settlement)
        return current

    @staticmethod
    def calculate_accrued_interest(
        settlement_date: date,
        maturity_date: date,
        coupon_rate: float,
        frequency: int = 1
    ) -> Tuple[float, date, date, int, int]:
        """
        Calculate accrued interest for a coupon bond.

        Returns:
            Tuple of (accrued_interest, prev_coupon_date, next_coupon_date, days_since, days_in_period)
        """
        # Get previous and next coupon dates
        prev_coupon = UMOAYieldCalculator.get_previous_coupon_date(
            settlement_date, maturity_date, frequency
        )

        # Next coupon is prev + period
        period_months = 12 // frequency
        year = prev_coupon.year
        month = prev_coupon.month + period_months
        day = prev_coupon.day

        while month > 12:
            month -= 12
            year += 1

        while True:
            try:
                next_coupon = date(year, month, day)
                break
            except ValueError:
                day -= 1

        # Calculate days
        days_since_coupon = (settlement_date - prev_coupon).days
        days_in_period = (next_coupon - prev_coupon).days

        # Accrued interest = coupon_rate * (days_since / days_in_period)
        accrued = coupon_rate * (days_since_coupon / days_in_period)

        return accrued, prev_coupon, next_coupon, days_since_coupon, days_in_period

    @staticmethod
    def calculate_oat_yield(
        clean_price: float,
        coupon_rate: float,
        settlement_date: date,
        maturity_date: date,
        frequency: int = 1,
        nominal_value: float = 100.0
    ) -> Optional[Tuple[float, float]]:
        """
        Calculate OAT Yield to Maturity using DIRTY PRICE.

        IMPORTANT: Yield is calculated on dirty price = clean_price + accrued_interest

        Returns:
            Tuple of (yield, accrued_interest) or None if calculation fails
        """
        try:
            days_to_maturity = (maturity_date - settlement_date).days
            if days_to_maturity <= 0:
                return None

            # Calculate accrued interest
            accrued, prev_coupon, next_coupon, days_since, days_in_period = \
                UMOAYieldCalculator.calculate_accrued_interest(
                    settlement_date, maturity_date, coupon_rate, frequency
                )

            # DIRTY PRICE = Clean Price + Accrued Interest
            dirty_price = clean_price + accrued

            print(f"  Previous coupon: {prev_coupon}")
            print(f"  Next coupon: {next_coupon}")
            print(f"  Days since coupon: {days_since}")
            print(f"  Days in period: {days_in_period}")
            print(f"  Accrued interest: {accrued:.4f}%")
            print(f"  Clean price: {clean_price:.4f}%")
            print(f"  Dirty price: {dirty_price:.4f}%")

            # Get remaining coupon dates
            coupon_dates = UMOAYieldCalculator.get_coupon_dates(
                settlement_date, maturity_date, frequency
            )

            if not coupon_dates:
                return None

            n_coupons = len(coupon_dates)
            coupon_payment = coupon_rate / frequency

            print(f"  Coupon dates: {[str(d) for d in coupon_dates]}")
            print(f"  Number of remaining coupons: {n_coupons}")

            # Initial guess using approximate formula
            years = days_to_maturity / 365.0
            approx_ytm = (coupon_rate + (100 - dirty_price) / years) / ((100 + dirty_price) / 2)
            y = approx_ytm / 100

            # Newton-Raphson iteration using DIRTY PRICE
            for iteration in range(100):
                pv = 0.0
                dpv = 0.0

                for i, coupon_date in enumerate(coupon_dates):
                    days = (coupon_date - settlement_date).days
                    t = days / 365.0

                    df = (1 + y) ** (-t)

                    cf = coupon_payment
                    if i == n_coupons - 1:
                        cf += 100  # Add principal at maturity

                    pv += cf * df
                    dpv -= cf * t * df / (1 + y)

                # Compare to DIRTY price
                diff = pv - dirty_price

                if abs(diff) < 1e-10:
                    break

                if abs(dpv) > 1e-15:
                    y = y - diff / dpv
                else:
                    break

                y = max(-0.5, min(2.0, y))

            ytm = y * 100

            print(f"  Calculated YTM: {ytm:.4f}%")

            return round(ytm, 4), round(accrued, 4)

        except Exception as e:
            print(f"OAT yield calculation error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def calculate_yield(
        price: Decimal,
        coupon_rate: Decimal,
        settlement_date: date,
        maturity_date: date,
        periodicity: str = 'A'
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """
        Calculate OAT yield and accrued interest.
        Returns (yield, accrued_interest) tuple.
        """
        frequency = 1 if periodicity == 'A' else 2

        result = UMOAYieldCalculator.calculate_oat_yield(
            clean_price=float(price),
            coupon_rate=float(coupon_rate),
            settlement_date=settlement_date,
            maturity_date=maturity_date,
            frequency=frequency
        )

        if result is not None:
            ytm, accrued = result
            return (
                Decimal(str(ytm)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                Decimal(str(accrued)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            )
        return None

    @staticmethod
    def time_to_maturity_years(settlement_date: date, maturity_date: date) -> Decimal:
        """Calculate time to maturity in years"""
        days = (maturity_date - settlement_date).days
        years = Decimal(str(days)) / Decimal('365')
        return years.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
