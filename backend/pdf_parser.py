import pdfplumber
import re
import os
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

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
        total_rows_before_filtering = 0
        total_candidate_rows = 0
        rows_with_valid_isin = 0
        rows_after_filtering = 0
        rows_fail_isin_validation = 0
        rows_fail_maturity_validation = 0
        rows_fail_security_type_validation = 0
        rows_fail_amount_parsing_validation = 0

        sample_isin_reject = None
        sample_maturity_reject = None
        sample_security_type_reject = None
        sample_amount_parsing_reject = None
        sample_candidate_rows = []
        sample_isin_fail_reasons = []

        isin_pattern = r'^[A-Z]{2}\d{10}$'

        logger.info("Starting PDF parse: filename=%s path=%s", os.path.basename(self.pdf_path), self.pdf_path)
        logger.info("ISIN validation pattern in use: %s", isin_pattern)

        with pdfplumber.open(self.pdf_path) as pdf:
            logger.info("PDF opened: filename=%s page_count=%d", os.path.basename(self.pdf_path), len(pdf.pages))
            for page_num, page in enumerate(pdf.pages):
                extracted_text = page.extract_text() or ''
                logger.info(
                    "Page %d text extracted: char_count=%d",
                    page_num + 1,
                    len(extracted_text)
                )

                # Skip cover pages
                if page_num < 2:
                    continue

                tables = page.extract_tables()
                if tables:
                    logger.info("Page %d tables found: count=%d", page_num + 1, len(tables))
                else:
                    logger.info("Page %d tables found: none", page_num + 1)

                for table in tables:
                    if table:
                        total_rows_before_filtering += len(table)
                    for row in table:
                        total_candidate_rows += 1

                        # Skip single-cell / blank rows; ISIN detection in col 0 is the real gate
                        if not row or len(row) < 8:
                            continue

                        if len(sample_candidate_rows) < 5:
                            sample_candidate_rows.append({
                                'page': page_num + 1,
                                'row_head': row[:8]
                            })

                        # Check if first cell is a valid ISIN
                        raw_isin_field = row[0] if len(row) > 0 else None
                        # Remove ALL whitespace (including embedded newlines from pdfplumber)
                        # then try exact match; if that fails, search within the cell content
                        raw_str = str(row[0]) if row[0] else ''
                        first_cell = re.sub(r'\s+', '', raw_str)

                        # If cleaning whitespace didn't produce a valid ISIN, try extracting one
                        if not re.match(isin_pattern, first_cell):
                            found = re.search(r'[A-Z]{2}\d{10}', raw_str)
                            if found:
                                first_cell = found.group()
                        if not re.match(isin_pattern, first_cell):
                            rows_fail_isin_validation += 1
                            if len(sample_isin_fail_reasons) < 5:
                                fail_reason = "regex_mismatch"
                                if raw_isin_field is None:
                                    fail_reason = "raw_field_none"
                                elif first_cell == "":
                                    fail_reason = "empty_after_strip"
                                elif len(first_cell) != 12:
                                    fail_reason = f"length_{len(first_cell)}_expected_12"
                                elif not re.match(r'^[A-Z]{2}', first_cell):
                                    fail_reason = "missing_2_leading_letters"
                                elif not re.match(r'^[A-Z]{2}\d+$', first_cell):
                                    fail_reason = "suffix_not_all_digits"

                                sample_isin_fail_reasons.append({
                                    'page': page_num + 1,
                                    'raw_isin_field': raw_isin_field,
                                    'normalized_isin_field': first_cell,
                                    'reason': fail_reason
                                })
                                logger.info(
                                    "ISIN_FAIL #%d page=%d reason=%s raw=%s cleaned=%s",
                                    rows_fail_isin_validation,
                                    page_num + 1,
                                    fail_reason,
                                    repr(raw_isin_field),
                                    repr(first_cell)
                                )
                            if sample_isin_reject is None:
                                sample_isin_reject = {
                                    'page': page_num + 1,
                                    'first_cell': first_cell,
                                    'row_head': row[:6]
                                }
                            continue
                        rows_with_valid_isin += 1

                        isin = first_cell
                        ncols = len(row)

                        def _cell(i):
                            return str(row[i]).strip() if ncols > i and row[i] is not None else None

                        # Two confirmed table formats:
                        #
                        # Old format (>=20 cols) — every-3-column layout:
                        #   [0] ISIN  [3] orig_mat  [6] remaining  [9] issue_date
                        #   [12] maturity  [15] outstanding  [18] coupon
                        #   [21] periodicity  [22] amortization
                        #
                        # New 17-col LTV format (<20 cols) — compact layout:
                        #   [0] ISIN  [2] orig_mat  [3] remaining  [6] issue_date
                        #   [7] maturity  [9] outstanding  [12] coupon
                        #   [13] periodicity  [14] amortization
                        if ncols >= 20:
                            original_maturity  = _cell(3)
                            remaining_duration = _cell(6)
                            issue_date_str     = _cell(9)
                            maturity_date_str  = _cell(12)
                            outstanding_str    = _cell(15)
                            coupon_str         = _cell(18) or ''
                            periodicity        = _cell(21) or 'A'
                            amortization_mode  = _cell(22)
                        else:
                            original_maturity  = _cell(2)
                            remaining_duration = _cell(3)
                            issue_date_str     = _cell(6)
                            maturity_date_str  = _cell(7)
                            outstanding_str    = _cell(9)
                            coupon_str         = _cell(12) or ''
                            periodicity        = _cell(13) or 'A'
                            amortization_mode  = _cell(14)

                        issue_date    = self.parse_date(issue_date_str)
                        maturity_date = self.parse_date(maturity_date_str)

                        outstanding_amount = None
                        if outstanding_str:
                            try:
                                outstanding_amount = float(outstanding_str.replace(',', '.'))
                            except ValueError:
                                rows_fail_amount_parsing_validation += 1
                                if sample_amount_parsing_reject is None:
                                    sample_amount_parsing_reject = {
                                        'page': page_num + 1,
                                        'isin': isin,
                                        'outstanding_raw': outstanding_str,
                                        'row_head': row[:6]
                                    }

                        coupon_rate = None
                        if coupon_str and re.match(r'^\d+[,\.]\d+$', coupon_str):
                            coupon_rate = float(coupon_str.replace(',', '.'))

                        # Skip if no maturity date
                        if not maturity_date:
                            rows_fail_maturity_validation += 1
                            if sample_maturity_reject is None:
                                sample_maturity_reject = {
                                    'page': page_num + 1,
                                    'isin': isin,
                                    'maturity_raw': maturity_date_str,
                                    'row_head': row[:6]
                                }
                            continue

                        rows_after_filtering += 1
                        # Classification: OAT if has coupon, BAT if no coupon
                        security_type = 'OAT' if coupon_rate is not None else 'BAT'
                        if security_type not in ('OAT', 'BAT'):
                            rows_fail_security_type_validation += 1
                            if sample_security_type_reject is None:
                                sample_security_type_reject = {
                                    'page': page_num + 1,
                                    'isin': isin,
                                    'coupon_raw': coupon_str,
                                    'derived_security_type': security_type,
                                    'row_head': row[:6]
                                }
                            continue

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

        logger.info(
            "PDF parse row counts: filename=%s rows_before_filtering=%d total_candidate_rows=%d rows_with_valid_isin=%d rows_after_filtering=%d extracted_securities=%d",
            os.path.basename(self.pdf_path),
            total_rows_before_filtering,
            total_candidate_rows,
            rows_with_valid_isin,
            rows_after_filtering,
            len(securities)
        )
        logger.info(
            "PDF parse validation failures: filename=%s fail_isin=%d fail_maturity=%d fail_security_type=%d fail_amount_parsing=%d",
            os.path.basename(self.pdf_path),
            rows_fail_isin_validation,
            rows_fail_maturity_validation,
            rows_fail_security_type_validation,
            rows_fail_amount_parsing_validation
        )
        logger.info("Sample candidate rows before ISIN validation (up to 5): %s", sample_candidate_rows)
        logger.info("Sample ISIN failure reasons (up to 5): %s", sample_isin_fail_reasons)
        logger.info("Sample raw field treated as ISIN: %s", sample_isin_fail_reasons[0]['raw_isin_field'] if sample_isin_fail_reasons else None)
        logger.info("Sample ISIN rejection: %s", sample_isin_reject)
        logger.info("Sample maturity rejection: %s", sample_maturity_reject)
        logger.info("Sample security_type rejection: %s", sample_security_type_reject)
        logger.info("Sample amount/parsing rejection: %s", sample_amount_parsing_reject)

        if len(securities) == 0:
            if total_candidate_rows == 0:
                drop_stage = "no candidate rows extracted from tables"
            elif rows_with_valid_isin == 0:
                drop_stage = "ISIN validation"
            elif rows_after_filtering == 0 and rows_fail_maturity_validation > 0:
                drop_stage = "maturity-date validation"
            elif rows_after_filtering == 0 and rows_fail_security_type_validation > 0:
                drop_stage = "security-type validation"
            elif rows_after_filtering == 0:
                drop_stage = "post-ISIN filtering (no rows reached output)"
            else:
                drop_stage = "unknown"

            logger.warning(
                "Parser rows dropped to zero at stage: filename=%s stage=%s counts={candidates:%d,valid_isin:%d,after_filter:%d}",
                os.path.basename(self.pdf_path),
                drop_stage,
                total_candidate_rows,
                rows_with_valid_isin,
                rows_after_filtering
            )
            logger.warning(
                "Parser returning empty result: filename=%s reason=no rows survived parsing/filtering",
                os.path.basename(self.pdf_path)
            )

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
