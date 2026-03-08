"""
Database Manager
Handles all database operations for UMOA securities
"""

import psycopg2
import numpy as np
import logging
import re
from psycopg2.extras import RealDictCursor
from datetime import date, datetime
from typing import List, Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    'BJ': 'Bénin',
    'BF': 'Burkina Faso',
    'CI': "Côte d'Ivoire",
    'GW': 'Guinée-Bissau',
    'ML': 'Mali',
    'NE': 'Niger',
    'SN': 'Sénégal',
    'TG': 'Togo',
}


def clean_remaining_duration(val):
    """Convert French-format duration strings like '0,21 ans' to float (e.g. 0.21).
    Returns None if conversion fails or val is empty."""
    if not val or not isinstance(val, str):
        return val
    val = val.replace(' ans', '').replace(',', '.').strip()
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class SecurityDatabaseManager:
    """Manages database operations for securities"""
    
    def __init__(self, db_config: Dict):
        self.config = db_config
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(**self.config)
            print("✓ Database connected successfully")
        except Exception as e:
            self.conn = None
            logger.exception("Database connection failed")
            raise
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")
    
    def process_upload(
        self,
        parsed_result: Dict,
        filename: str,
        uploaded_by: str = 'admin'
    ) -> Dict:
        """Process parsed PDF data and update database.

        parsed_result is the dict returned by UMOATitresPDFParser.parse():
            {'securities': [{'isin', 'country_code', 'maturity_date', ...}], 'total_count': N}
        """
        securities = parsed_result.get('securities', [])
        stats = {
            'added': 0,
            'updated': 0,
            'deprecated': 0,
            'errors': [],
            'total_processed': 0
        }

        # Collect all ISINs present in this upload — used later to deprecate stale records
        new_isins = [sec['isin'] for sec in securities if sec.get('isin')]

        start_time = datetime.now()
        cursor = self.conn.cursor()

        try:
            print(f"\nProcessing {len(securities)} securities...")

            # 1. Deprecate securities that have passed their maturity date
            deprecated_count = self.deprecate_matured_securities(cursor)
            stats['deprecated'] = deprecated_count
            if deprecated_count > 0:
                print(f"  → Deprecated {deprecated_count} matured securities")

            # 2. Process each security from PDF (INSERT new, UPDATE existing).
            #    Each row is guarded by its own savepoint so a single bad row
            #    does not roll back the rows already written.
            for sec in securities:
                isin_code = sec.get('isin', 'unknown')
                cursor.execute("SAVEPOINT sp_security")
                try:
                    cursor.execute(
                        "SELECT id FROM securities WHERE isin_code = %s",
                        (isin_code,)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        self.update_security(cursor, sec, filename)
                        stats['updated'] += 1
                    else:
                        self.insert_security(cursor, sec, filename)
                        stats['added'] += 1

                    stats['total_processed'] += 1
                    cursor.execute("RELEASE SAVEPOINT sp_security")

                except Exception as e:
                    cursor.execute("ROLLBACK TO SAVEPOINT sp_security")
                    error_msg = f"Error processing {isin_code}: {str(e)}"
                    stats['errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")

            # 3. Retire any previously-active securities NOT present in this upload.
            #    Uses a savepoint so a failure here never rolls back the inserts/updates.
            if new_isins:
                cursor.execute("SAVEPOINT sp_retirement")
                try:
                    cursor.execute("""
                        UPDATE securities
                        SET status = 'redeemed',
                            deprecated_at = NOW(),
                            updated_at = NOW()
                        WHERE status = 'active'
                          AND isin_code != ALL(%s)
                    """, (new_isins,))
                    stale_count = cursor.rowcount
                    stats['deprecated'] += stale_count
                    cursor.execute("RELEASE SAVEPOINT sp_retirement")
                    if stale_count > 0:
                        print(f"  → Retired {stale_count} stale securities not in this upload")
                except Exception as e:
                    cursor.execute("ROLLBACK TO SAVEPOINT sp_retirement")
                    print(f"  ⚠️  Could not retire stale securities: {e}")
                    stats['errors'].append(f"Stale retirement failed: {e}")

            # 4. Log upload
            duration = (datetime.now() - start_time).total_seconds()
            pdf_date = securities[0].get('maturity_date') if securities else None

            cursor.execute("SAVEPOINT sp_log")
            try:
                self.log_upload(cursor, filename, uploaded_by, stats, duration, pdf_date)
                cursor.execute("RELEASE SAVEPOINT sp_log")
            except Exception as e:
                cursor.execute("ROLLBACK TO SAVEPOINT sp_log")
                print(f"  ⚠️  Could not log upload: {e}")

            self.conn.commit()

            print(f"\n✓ Upload processed successfully")
            print(f"  → Added: {stats['added']}")
            print(f"  → Updated: {stats['updated']}")
            print(f"  → Deprecated: {stats['deprecated']}")

        except Exception as e:
            self.conn.rollback()
            error_msg = f"Database error: {str(e)}"
            stats['errors'].append(error_msg)
            print(f"\n✗ {error_msg}")
            raise

        finally:
            cursor.close()

        return stats
    
    def deprecate_matured_securities(self, cursor) -> int:
        """Mark securities past maturity as deprecated"""
        today = date.today()
        
        cursor.execute("""
            UPDATE securities 
            SET status = 'matured',
                deprecated_at = NOW(),
                updated_at = NOW()
            WHERE maturity_date < %s 
              AND status = 'active'
        """, (today,))
        
        return cursor.rowcount
    
    def insert_security(self, cursor, sec: Dict, source_file: str):
        """Insert new security from parser dict."""
        isin_code = sec['isin']
        country_code = sec.get('country_code', isin_code[:2])
        cursor.execute("""
            INSERT INTO securities (
                isin_code, short_code, country_code, country_name,
                security_type, original_maturity, issue_date, maturity_date,
                remaining_duration, coupon_rate, outstanding_amount,
                periodicity, amortization_mode, deferred_years,
                status, source_file
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            isin_code,
            isin_code[8:],                                   # last 4 digits = short_code
            country_code,
            COUNTRY_NAMES.get(country_code, country_code),  # country_name lookup
            sec.get('security_type'),
            sec.get('original_maturity'),
            sec.get('issue_date'),
            sec.get('maturity_date'),
            clean_remaining_duration(sec.get('remaining_duration')),
            sec.get('coupon_rate'),
            sec.get('outstanding_amount'),
            (sec.get('periodicity') or 'A')[:1],          # varchar(1) — truncate to first char
            (sec.get('amortization_mode') or '')[:5] or None,  # varchar(5)
            None,           # deferred_years not extracted by parser
            'active',
            source_file
        ))

    def update_security(self, cursor, sec: Dict, source_file: str):
        """Update existing security from parser dict."""
        cursor.execute("""
            UPDATE securities
            SET maturity_date = %s,
                remaining_duration = %s,
                coupon_rate = %s,
                outstanding_amount = %s,
                original_maturity = %s,
                security_type = %s,
                updated_at = NOW(),
                status = 'active',
                source_file = %s
            WHERE isin_code = %s
        """, (
            sec.get('maturity_date'),
            clean_remaining_duration(sec.get('remaining_duration')),
            sec.get('coupon_rate'),
            sec.get('outstanding_amount'),
            sec.get('original_maturity'),
            sec.get('security_type'),
            source_file,
            sec['isin']
        ))
    
    def log_upload(
        self, cursor, filename: str, uploaded_by: str, 
        stats: Dict, duration: float, pdf_date: Optional[date]
    ):
        """Log upload in history table"""
        cursor.execute("""
            INSERT INTO upload_history (
                filename, uploaded_by, records_added, records_updated,
                records_deprecated, total_processed, processing_status,
                error_log, processing_duration, pdf_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            filename, uploaded_by, stats['added'], stats['updated'],
            stats['deprecated'], stats['total_processed'],
            'success' if not stats['errors'] else 'partial',
            '\n'.join(stats['errors']) if stats['errors'] else None,
            int(duration),
            pdf_date
        ))
    
    def search_by_shortcode(
        self, 
        short_code: str, 
        country_code: Optional[str] = None
    ) -> List[Dict]:
        """Search for securities by last 4 digits"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        if country_code:
            cursor.execute("""
                SELECT * FROM securities 
                WHERE short_code = %s 
                  AND country_code = %s
                  AND status = 'active'
                ORDER BY maturity_date
            """, (short_code, country_code.upper()))
        else:
            cursor.execute("""
                SELECT * FROM securities 
                WHERE short_code = %s
                  AND status = 'active'
                ORDER BY country_code, maturity_date
            """, (short_code,))
        
        results = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in results]
    
    def search_by_isin(self, isin_code: str) -> Optional[Dict]:
        """Search for security by full ISIN code"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM securities 
            WHERE isin_code = %s
              AND status = 'active'
        """, (isin_code.upper(),))
        
        result = cursor.fetchone()
        cursor.close()
        
        return dict(result) if result else None

    def search_by_isin_flexible(self, isin: str) -> Optional[Dict]:
        """Search by full ISIN (SN0000001223) or abbreviated format (SN1223)"""
        isin = isin.upper().strip()

        # Full ISIN pattern: 2 letters + 10 digits
        full_pattern = r'^([A-Z]{2})(\d{10})$'
        # Abbreviated pattern: 2 letters + 4 digits
        abbrev_pattern = r'^([A-Z]{2})(\d{4})$'

        if re.match(full_pattern, isin):
            return self.search_by_isin(isin)
        elif re.match(abbrev_pattern, isin):
            country_code = isin[:2]
            short_code = isin[2:]
            results = self.search_by_shortcode(short_code, country_code)
            return results[0] if results else None
        return None

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_securities,
                COUNT(DISTINCT country_code) as countries,
                SUM(CASE WHEN security_type = 'OAT' THEN 1 ELSE 0 END) as oat_count,
                SUM(CASE WHEN security_type = 'BAT' THEN 1 ELSE 0 END) as bat_count,
                MAX(updated_at) as last_update
            FROM securities
            WHERE status = 'active'
        """)
        
        result = cursor.fetchone()
        cursor.close()
        
        return {
            'total_securities': result[0],
            'countries': result[1],
            'oat_count': result[2],
            'bat_count': result[3],
            'last_update': result[4]
        }
    
    def get_upload_history(self, limit: int = 10) -> List[Dict]:
        """Get recent upload history"""
        if self.conn is None:
            self.connect()
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT * FROM upload_history
            ORDER BY upload_date DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()

        return [dict(row) for row in results]

    def fix_security_classifications(self) -> Dict:
        """
        Fix misclassified securities based on coupon_rate rule:
        - OAT: has valid coupon_rate (NOT NULL and NOT NaN)
        - BAT: no coupon_rate (NULL or NaN)

        Also converts NaN coupon_rate values to NULL for consistency.
        Returns stats about what was fixed.
        """
        cursor = self.conn.cursor()
        stats = {
            'nan_to_null': 0,
            'bat_to_oat': 0,
            'oat_to_bat': 0,
            'already_correct': 0,
            'total_checked': 0
        }

        try:
            # First, convert any NaN coupon_rate values to NULL
            # For PostgreSQL numeric type, use 'NaN'::numeric comparison
            cursor.execute("""
                UPDATE securities
                SET coupon_rate = NULL,
                    updated_at = NOW()
                WHERE coupon_rate = 'NaN'::numeric
                  AND status = 'active'
            """)
            stats['nan_to_null'] = cursor.rowcount
            if stats['nan_to_null'] > 0:
                print(f"  → Converted {stats['nan_to_null']} NaN coupon_rate values to NULL")

            # Find BATs that should be OATs (have valid coupon_rate)
            cursor.execute("""
                UPDATE securities
                SET security_type = 'OAT',
                    updated_at = NOW()
                WHERE security_type = 'BAT'
                  AND coupon_rate IS NOT NULL
                  AND status = 'active'
            """)
            stats['bat_to_oat'] = cursor.rowcount

            # Find OATs that should be BATs (no coupon_rate)
            cursor.execute("""
                UPDATE securities
                SET security_type = 'BAT',
                    updated_at = NOW()
                WHERE security_type = 'OAT'
                  AND coupon_rate IS NULL
                  AND status = 'active'
            """)
            stats['oat_to_bat'] = cursor.rowcount

            # Count total active securities
            cursor.execute("SELECT COUNT(*) FROM securities WHERE status = 'active'")
            stats['total_checked'] = cursor.fetchone()[0]
            stats['already_correct'] = stats['total_checked'] - stats['bat_to_oat'] - stats['oat_to_bat']

            self.conn.commit()

            print(f"\n✓ Security classification fix complete:")
            print(f"  → NaN → NULL: {stats['nan_to_null']}")
            print(f"  → BAT → OAT (had coupon): {stats['bat_to_oat']}")
            print(f"  → OAT → BAT (no coupon): {stats['oat_to_bat']}")
            print(f"  → Already correct: {stats['already_correct']}")
            print(f"  → Total checked: {stats['total_checked']}")

        except Exception as e:
            self.conn.rollback()
            print(f"\n✗ Classification fix failed: {e}")
            raise
        finally:
            cursor.close()

        return stats

    # ============================================
    # Yield Curve Methods
    # ============================================

    def save_yield_curves(self, data: List[Dict], filename: str) -> Dict:
        """Save yield curve data from Excel upload.

        Uses a single timestamp for all rows in this batch.
        Deletes any existing data first to allow fresh uploads.
        Deduplicates by (country_code, maturity_years) keeping first occurrence.
        """
        cursor = self.conn.cursor()
        stats = {'inserted': 0, 'duplicates_removed': 0, 'errors': []}

        try:
            # Delete ALL existing yield curve data (fresh upload replaces everything)
            cursor.execute("DELETE FROM yield_curves")
            deleted = cursor.rowcount
            if deleted > 0:
                print(f"  Cleared {deleted} existing yield curve rows")

            # Deduplicate data by (country_code, maturity_years) - keep first occurrence
            seen = set()
            unique_data = []
            for row in data:
                key = (row['country_code'], row['maturity_years'])
                if key not in seen:
                    seen.add(key)
                    unique_data.append(row)
                else:
                    stats['duplicates_removed'] += 1

            if stats['duplicates_removed'] > 0:
                print(f"  Removed {stats['duplicates_removed']} duplicate entries")

            # Get current timestamp for this batch
            from datetime import datetime
            upload_time = datetime.now()

            # Prepare all values for batch insert
            values = []
            for row in unique_data:
                values.append((
                    row['country_code'],
                    row['maturity_years'],
                    row.get('zero_coupon_rate'),
                    row.get('oat_rate'),
                    filename,
                    upload_time
                ))

            # Batch insert using executemany
            from psycopg2.extras import execute_values
            execute_values(
                cursor,
                """INSERT INTO yield_curves
                   (country_code, maturity_years, zero_coupon_rate, oat_rate, excel_filename, upload_date)
                   VALUES %s""",
                values
            )
            stats['inserted'] = len(values)

            self.conn.commit()
            print(f"  Inserted {stats['inserted']} yield curve points")

        except Exception as e:
            self.conn.rollback()
            stats['errors'].append(f"Transaction error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            cursor.close()

        return stats

    def get_yield_curve(self, country_code: str) -> List[Dict]:
        """Get latest yield curve for a country"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        # Get the most recent upload date for this country
        cursor.execute("""
            SELECT DISTINCT upload_date
            FROM yield_curves
            WHERE country_code = %s
            ORDER BY upload_date DESC
            LIMIT 1
        """, (country_code.upper(),))

        latest = cursor.fetchone()
        if not latest:
            cursor.close()
            return []

        # Get all data points for that upload date
        cursor.execute("""
            SELECT maturity_years, zero_coupon_rate, oat_rate, upload_date
            FROM yield_curves
            WHERE country_code = %s AND upload_date = %s
            ORDER BY maturity_years
        """, (country_code.upper(), latest['upload_date']))

        results = cursor.fetchall()
        cursor.close()

        return [dict(row) for row in results]

    def get_market_rate(self, country_code: str, maturity_years: float, security_type: str) -> Optional[Dict]:
        """Get market rate for comparison, matching closest maturity bucket"""
        curve = self.get_yield_curve(country_code)
        if not curve:
            return None

        # Match to closest maturity bucket
        bucket = self._match_maturity_bucket(maturity_years)

        # Find the rate for this bucket
        for point in curve:
            if abs(float(point['maturity_years']) - bucket) < 0.01:
                rate = point['oat_rate'] if security_type == 'OAT' else point['zero_coupon_rate']
                return {
                    'market_rate': float(rate) if rate else None,
                    'matched_maturity': bucket,
                    'upload_date': point['upload_date']
                }

        return None

    def _match_maturity_bucket(self, years: float) -> float:
        """Match years to maturity to the nearest standard bucket"""
        if years < 0.4:
            return 0.25   # 3 mois
        elif years < 0.7:
            return 0.5    # 6 mois
        elif years < 0.9:
            return 0.75   # 9 mois
        elif years < 1.5:
            return 1.0    # 1 an
        elif years < 2.5:
            return 2.0    # 2 ans
        elif years < 3.5:
            return 3.0    # 3 ans
        elif years < 4.5:
            return 4.0    # 4 ans
        elif years < 5.5:
            return 5.0    # 5 ans
        elif years < 6.5:
            return 6.0    # 6 ans
        elif years < 7.5:
            return 7.0    # 7 ans
        elif years < 8.5:
            return 8.0    # 8 ans
        elif years < 9.5:
            return 9.0    # 9 ans
        else:
            return 10.0   # 10 ans

    def get_excel_upload_history(self, limit: int = 10) -> List[Dict]:
        """Get recent Excel upload history"""
        if self.conn is None:
            self.connect()
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT
                excel_filename as filename,
                upload_date,
                'success' as status,
                COUNT(*) as records
            FROM yield_curves
            GROUP BY excel_filename, upload_date
            ORDER BY upload_date DESC
            LIMIT %s
        """, (limit,))

        results = cursor.fetchall()
        cursor.close()

        return [dict(row) for row in results]