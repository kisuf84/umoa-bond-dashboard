import pdfplumber
import re
from datetime import datetime
from typing import Dict, List

class UMOATitresPDFParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        
    def parse_date(self, date_str: str) -> str:
        """Convert French date format to ISO format"""
        if not date_str:
            return None
            
        months = {
            'janv': '01', 'févr': '02', 'mars': '03', 'avr': '04',
            'mai': '05', 'juin': '06', 'juil': '07', 'août': '08',
            'sept': '09', 'oct': '10', 'nov': '11', 'déc': '12'
        }
        
        match = re.match(r'(\d{1,2})\.(janv|févr|mars|avr|mai|juin|juil|août|sept|oct|nov|déc)\.(\d{2})', str(date_str))
        if match:
            day, month, year = match.groups()
            year = '20' + year if int(year) <= 50 else '19' + year
            return f"{year}-{months[month]}-{day.zfill(2)}"
        return None
    
    def parse(self) -> Dict:
        """
        Parse UMOA Titres PDF and extract bond data.

        Table structure (column indices):
        [0]:  ISIN code
        [3]:  Original maturity (e.g., '3 ans')
        [6]:  Remaining duration (e.g., '0,12 ans')
        [9]:  Issue date
        [12]: Maturity date
        [15]: Outstanding amount (billions)
        [18]: Coupon rate (%) - EMPTY for BAT, has value for OAT
        [21]: Periodicity ('A' = Annual)
        [22]: Amortization mode ('IF')

        Classification rule:
        - OAT: Has coupon rate (cell[18] is not empty)
        - BAT: No coupon rate (cell[18] is empty)
        """
        securities = []

        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Skip cover pages
                if page_num < 2:
                    continue

                tables = page.extract_tables()

                for table in tables:
                    for row in table:
                        # Need at least 20 columns for full data
                        if not row or len(row) < 20:
                            continue

                        # Check if first cell is a valid ISIN
                        first_cell = str(row[0]).strip() if row[0] else ''
                        if not re.match(r'^[A-Z]{2}\d{10}$', first_cell):
                            continue

                        isin = first_cell

                        # Extract data from known column positions
                        # Original maturity: cell[3]
                        original_maturity = str(row[3]).strip() if row[3] else None

                        # Remaining duration: cell[6]
                        remaining_duration = str(row[6]).strip() if row[6] else None

                        # Issue date: cell[9]
                        issue_date_str = str(row[9]).strip() if row[9] else None
                        issue_date = self.parse_date(issue_date_str)

                        # Maturity date: cell[12]
                        maturity_date_str = str(row[12]).strip() if row[12] else None
                        maturity_date = self.parse_date(maturity_date_str)

                        # Outstanding amount: cell[15]
                        outstanding_str = str(row[15]).strip() if row[15] else None
                        outstanding_amount = None
                        if outstanding_str:
                            try:
                                outstanding_amount = float(outstanding_str.replace(',', '.'))
                            except ValueError:
                                pass

                        # Coupon rate: cell[18] - THIS IS THE KEY FIELD
                        coupon_str = str(row[18]).strip() if row[18] else ''
                        coupon_rate = None
                        if coupon_str and re.match(r'^\d+[,\.]\d+$', coupon_str):
                            coupon_rate = float(coupon_str.replace(',', '.'))

                        # Periodicity: cell[21]
                        periodicity = str(row[21]).strip() if len(row) > 21 and row[21] else 'A'

                        # Amortization mode: cell[22]
                        amortization_mode = str(row[22]).strip() if len(row) > 22 and row[22] else None

                        # Skip if no maturity date
                        if not maturity_date:
                            continue

                        # Classification: OAT if has coupon, BAT if no coupon
                        security_type = 'OAT' if coupon_rate is not None else 'BAT'

                        securities.append({
                            'isin': isin,
                            'country_code': isin[:2],
                            'issue_date': issue_date,
                            'maturity_date': maturity_date,
                            'coupon_rate': coupon_rate,
                            'security_type': security_type,
                            'original_maturity': original_maturity,
                            'remaining_duration': remaining_duration,
                            'outstanding_amount': outstanding_amount,
                            'periodicity': periodicity,
                            'amortization_mode': amortization_mode
                        })

        return {
            'securities': securities,
            'total_count': len(securities)
        }

if __name__ == '__main__':
    import sys

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else '/Users/IssoufK/Downloads/UT-LTV-31.12.2025.pdf'
    print(f"Parsing: {pdf_path}")

    parser = UMOATitresPDFParser(pdf_path)
    data = parser.parse()

    print(f"\n{'='*60}")
    print(f"PARSING RESULTS")
    print(f"{'='*60}")

    bat_count = sum(1 for s in data['securities'] if s['security_type'] == 'BAT')
    oat_count = sum(1 for s in data['securities'] if s['security_type'] == 'OAT')

    print(f"\nTotal securities: {data['total_count']}")
    print(f"  OAT (has coupon): {oat_count}")
    print(f"  BAT (no coupon):  {bat_count}")

    # Verify classification rule
    oat_with_coupon = sum(1 for s in data['securities'] if s['security_type'] == 'OAT' and s['coupon_rate'])
    oat_without_coupon = sum(1 for s in data['securities'] if s['security_type'] == 'OAT' and not s['coupon_rate'])
    bat_with_coupon = sum(1 for s in data['securities'] if s['security_type'] == 'BAT' and s['coupon_rate'])
    bat_without_coupon = sum(1 for s in data['securities'] if s['security_type'] == 'BAT' and not s['coupon_rate'])

    print(f"\nClassification verification:")
    print(f"  OAT with coupon: {oat_with_coupon} {'✓' if oat_with_coupon == oat_count else '✗'}")
    print(f"  OAT without coupon: {oat_without_coupon} {'✓' if oat_without_coupon == 0 else '✗ ERROR'}")
    print(f"  BAT with coupon: {bat_with_coupon} {'✗ ERROR' if bat_with_coupon > 0 else '✓'}")
    print(f"  BAT without coupon: {bat_without_coupon} {'✓' if bat_without_coupon == bat_count else '✗'}")

    # Show sample OATs
    print(f"\nSample OAT bonds (should have coupon):")
    oat_samples = [s for s in data['securities'] if s['security_type'] == 'OAT'][:5]
    for sec in oat_samples:
        print(f"  {sec['isin']}: coupon={sec['coupon_rate']}%, maturity={sec['maturity_date']}")

    # Show sample BATs
    print(f"\nSample BAT bonds (should have NO coupon):")
    bat_samples = [s for s in data['securities'] if s['security_type'] == 'BAT'][:5]
    for sec in bat_samples:
        print(f"  {sec['isin']}: coupon={sec['coupon_rate']}, maturity={sec['maturity_date']}")

    # Check specific bonds mentioned by user
    print(f"\nSpecific bond checks:")
    for isin in ['TG0000001981', 'TG0000001551']:
        bond = next((s for s in data['securities'] if s['isin'] == isin), None)
        if bond:
            print(f"  {isin}: type={bond['security_type']}, coupon={bond['coupon_rate']}")
        else:
            print(f"  {isin}: NOT FOUND")
