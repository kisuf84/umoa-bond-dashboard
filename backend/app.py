"""
UMOA Bond Intelligence Dashboard API
Flask application for bond search and yield calculation
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from datetime import date, datetime
from decimal import Decimal
import traceback
from collections import defaultdict

from pdf_parser import UMOATitresPDFParser
from database_manager import SecurityDatabaseManager
from yield_calculator import UMOAYieldCalculator
from excel_parser import YieldCurveExcelParser

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database connection
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'umoa_bonds'),
    'user': os.getenv('DB_USER', 'IssoufK'),
    'password': os.getenv('DB_PASSWORD', '')
}

db_manager = SecurityDatabaseManager(db_config)

# ============ SEARCH ANALYTICS (In-Memory) ============
search_analytics = {
    'by_country': defaultdict(int),
    'by_isin': defaultdict(int),
    'total_searches': 0
}

def track_search(country_code, isin_code=None):
    """Track search analytics"""
    search_analytics['total_searches'] += 1
    if country_code:
        search_analytics['by_country'][country_code] += 1
    if isin_code:
        search_analytics['by_isin'][isin_code] += 1

# Helper functions
import math
import re

def serialize_value(value):
    """Convert Decimal, date, NaN values to JSON-serializable formats"""
    # Handle None
    if value is None:
        return None
    # Handle numpy NaN/inf
    try:
        import numpy as np
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
            return None
    except (ImportError, TypeError):
        pass
    # Handle Python float NaN/inf
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    # Handle Decimal - convert to float and check for NaN
    if isinstance(value, Decimal):
        float_val = float(value)
        if math.isnan(float_val) or math.isinf(float_val):
            return None
        return float_val
    # Handle date/datetime
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

def serialize_dict(data: dict) -> dict:
    """Serialize all values in a dictionary, converting NaN to null"""
    return {k: serialize_value(v) for k, v in data.items()}


def get_market_comparison(country_code: str, maturity_years: float, security_type: str, calculated_yield: float) -> dict:
    """
    Get market rate comparison for yield intelligence.
    Returns comparison data with spread and recommendation.
    """
    try:
        market_data = db_manager.get_market_rate(country_code, maturity_years, security_type)

        if not market_data or market_data.get('market_rate') is None:
            return None

        market_rate = market_data['market_rate']
        spread = round(calculated_yield - market_rate, 2)
        abs_spread = abs(spread)

        # Determine rating and recommendation
        if abs_spread <= 0.5:
            rating = 'fair'
            recommendation = 'Fair market pricing'
        elif spread < 0:
            # Below market = discount (attractive for buyers)
            rating = 'discount'
            recommendation = 'This bond trades at a DISCOUNT to market - Potentially attractive'
        else:
            # Above market = premium
            rating = 'premium'
            recommendation = 'This bond trades at a PREMIUM to market - Review carefully'

        # Format spread text
        if spread < 0:
            spread_text = f'{abs_spread:.2f}% below market'
        elif spread > 0:
            spread_text = f'{abs_spread:.2f}% above market'
        else:
            spread_text = 'At market rate'

        return {
            'market_rate': round(market_rate, 2),
            'spread': spread,
            'spread_text': spread_text,
            'rating': rating,
            'recommendation': recommendation,
            'matched_maturity': market_data.get('matched_maturity'),
            'yield_curve_date': market_data['upload_date'].strftime('%Y-%m-%d') if market_data.get('upload_date') else None
        }
    except Exception as e:
        print(f"Market comparison error: {e}")
        return None

# ============ HEALTH CHECK ============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        stats = db_manager.get_statistics()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'total_securities': stats['total_securities']
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

# ============ SEARCH ENDPOINTS ============

@app.route('/api/search', methods=['POST'])
def search_bonds():
    """
    Search for bonds by ISIN code

    Accepted formats:
    - Full ISIN: "BF0000001792" (2 letter country code + 10 digits)
    - Abbreviated: "BF1792" (2 letter country code + 4 digit shortcode)

    Request body:
    {
        "query": "BF0000001792" or "BF1792"
    }
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip().upper()

        if not query:
            return jsonify({'error': 'Query required'}), 400

        # Validate format: must be CC + digits only
        # Full ISIN: XX0000001234 (12 chars: 2 letters + 10 digits)
        # Abbreviated: XX1234 (6 chars: 2 letters + 4 digits)

        full_isin_pattern = re.compile(r'^([A-Z]{2})(\d{10})$')
        abbreviated_pattern = re.compile(r'^([A-Z]{2})(\d{4})$')

        full_match = full_isin_pattern.match(query)
        abbrev_match = abbreviated_pattern.match(query)

        if full_match:
            # Full ISIN format: BF0000001792
            country_code = full_match.group(1)
            digits = full_match.group(2)
            short_code = digits[-4:]  # Last 4 digits
        elif abbrev_match:
            # Abbreviated format: BF1792
            country_code = abbrev_match.group(1)
            short_code = abbrev_match.group(2)
        else:
            return jsonify({
                'error': 'Invalid format. Use full ISIN (e.g., BF0000001792) or abbreviated (e.g., BF1792)'
            }), 400

        # Search database
        results = db_manager.search_by_shortcode(
            short_code=short_code,
            country_code=country_code
        )

        # Track search analytics
        if results:
            for r in results:
                track_search(r.get('country_code'), r.get('isin_code'))
        else:
            track_search(country_code)

        if not results:
            return jsonify({
                'found': False,
                'message': f"No active securities found for {country_code}{short_code}"
            })

        # Serialize results
        formatted_results = [serialize_dict(r) for r in results]

        return jsonify({
            'found': True,
            'count': len(formatted_results),
            'results': formatted_results
        })

    except Exception as e:
        print(f"Search error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============ YIELD CALCULATOR ENDPOINTS ============

@app.route('/api/calculate-yield', methods=['POST'])
def calculate_yield():
    """
    Calculate yield for a bond

    Request body:
    {
        "isin": "CI0000001234",
        "price": 97.5,
        "settlement_date": "2026-01-26" (optional, defaults to today)
    }
    """
    try:
        data = request.get_json()
        isin = data.get('isin')
        price = data.get('price')
        settlement_date_str = data.get('settlement_date')

        if not isin:
            return jsonify({'error': 'ISIN is required'}), 400

        # Normalize price - handle tuple/list/string cases
        if isinstance(price, (list, tuple)):
            price = price[0]  # Extract first element if it's a collection
        elif price is None:
            return jsonify({'error': 'Price is required'}), 400

        # Convert to float safely
        try:
            price_float = float(str(price).strip())
        except (ValueError, TypeError) as e:
            return jsonify({'error': f'Invalid price format: {price}'}), 400

        # Validate price range (bonds typically trade between 0-200% of par)
        if price_float <= 0 or price_float > 200:
            return jsonify({'error': f'Price must be between 0 and 200, got {price_float}'}), 400

        # Get bond details from database (supports both full and abbreviated ISIN)
        bond = db_manager.search_by_isin_flexible(isin)

        if not bond:
            return jsonify({'error': 'Bond not found'}), 404

        # Parse settlement date
        if settlement_date_str:
            settlement_date = datetime.strptime(settlement_date_str, '%Y-%m-%d').date()
        else:
            settlement_date = date.today()

        # Check if bond is OAT (has coupon) or BAT (no coupon)
        coupon_rate = bond.get('coupon_rate')
        if coupon_rate is None:
            # BAT (zero-coupon bond) - calculate simple yield with ACT/360
            days_to_maturity = (bond['maturity_date'] - settlement_date).days
            if days_to_maturity <= 0:
                return jsonify({'error': 'Bond has matured'}), 400

            # BAT Yield = ((Nominal/Price) - 1) × (360/Days) × 100
            # Using ACT/360 convention for money market instruments
            calculated_yield = UMOAYieldCalculator.calculate_bat_yield(
                price=price_float,
                settlement_date=settlement_date,
                maturity_date=bond['maturity_date']
            )
            if calculated_yield is None:
                return jsonify({'error': 'Could not calculate yield'}), 500
            time_to_maturity_years = round(days_to_maturity / 365, 2)

            # Get market comparison
            market_comparison = get_market_comparison(
                bond['country_code'], time_to_maturity_years, 'BAT', calculated_yield
            )

            return jsonify({
                'isin': isin,
                'price': price_float,
                'yield': calculated_yield,
                'yield_type': 'Discount Yield',
                'coupon_rate': 0,
                'maturity_date': bond['maturity_date'].isoformat(),
                'days_to_maturity': days_to_maturity,
                'time_to_maturity_years': time_to_maturity_years,
                'settlement_date': settlement_date.isoformat(),
                'country': bond['country_name'],
                'security_type': bond['security_type'],
                'accrued_interest': 0,
                'market_comparison': market_comparison
            })

        # OAT (coupon-bearing bond) - calculate YTM
        # Debug logging
        print(f"\n{'='*50}")
        print(f"YIELD CALCULATION DEBUG")
        print(f"{'='*50}")
        print(f"Settlement Date (raw input): {settlement_date_str}")
        print(f"Settlement Date (parsed): {settlement_date}")
        print(f"Maturity Date: {bond['maturity_date']}")
        print(f"Coupon Rate: {coupon_rate}%")
        print(f"Price: {price_float}%")
        print(f"Days to Maturity: {(bond['maturity_date'] - settlement_date).days}")
        print(f"{'='*50}")

        ytm = UMOAYieldCalculator.calculate_yield(
            price=Decimal(str(price_float)),
            coupon_rate=coupon_rate,
            settlement_date=settlement_date,
            maturity_date=bond['maturity_date'],
            periodicity=bond.get('periodicity', 'A')
        )

        print(f"Calculated YTM: {ytm}%")
        print(f"{'='*50}\n")

        if ytm is None:
            return jsonify({'error': 'Could not calculate yield'}), 500

        # Calculate time to maturity
        days_to_maturity = (bond['maturity_date'] - settlement_date).days
        time_to_maturity = UMOAYieldCalculator.time_to_maturity_years(
            settlement_date, bond['maturity_date']
        )

        # Calculate accrued interest (Actual/Actual day count convention)
        # For annual coupon, find days since last coupon
        issue_date = bond.get('issue_date')
        if issue_date:
            # Calculate days since last coupon payment
            # Assuming annual coupon on anniversary of issue date
            last_coupon_date = issue_date.replace(year=settlement_date.year)
            if last_coupon_date > settlement_date:
                last_coupon_date = last_coupon_date.replace(year=settlement_date.year - 1)
            next_coupon_date = last_coupon_date.replace(year=last_coupon_date.year + 1)

            days_since_coupon = (settlement_date - last_coupon_date).days
            days_in_period = (next_coupon_date - last_coupon_date).days

            # Accrued Interest = (Coupon Rate / 100) * (Days Since Last Coupon / Days in Period) * 100
            accrued_interest = float(coupon_rate) * (days_since_coupon / days_in_period)
        else:
            accrued_interest = 0

        # Unpack tuple if yield calculator returns (yield, accrued)
        if isinstance(ytm, tuple):
            calculated_yield = float(ytm[0])
        else:
            calculated_yield = float(ytm)

        # Get market comparison
        market_comparison = get_market_comparison(
            bond['country_code'], float(time_to_maturity), 'OAT', calculated_yield
        )

        return jsonify({
            'isin': isin,
            'price': price_float,
            'yield': calculated_yield,
            'yield_type': 'Yield to Maturity',
            'coupon_rate': float(coupon_rate) if coupon_rate else 0,
            'maturity_date': bond['maturity_date'].isoformat(),
            'days_to_maturity': days_to_maturity,
            'time_to_maturity_years': float(time_to_maturity),
            'settlement_date': settlement_date.isoformat(),
            'country': bond['country_name'],
            'security_type': bond['security_type'],
            'accrued_interest': round(accrued_interest, 4),
            'market_comparison': market_comparison
        })

    except Exception as e:
        print(f"Yield calculation error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/bond/<isin>', methods=['GET'])
def get_bond_details(isin):
    """Get bond details by ISIN for yield calculator auto-fill (supports both formats)"""
    try:
        bond = db_manager.search_by_isin_flexible(isin.upper())
        if not bond:
            return jsonify({'error': 'Bond not found'}), 404

        return jsonify({
            'found': True,
            'bond': serialize_dict(bond)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ PDF UPLOAD ENDPOINTS ============

@app.route('/api/upload-pdf', methods=['POST'])
def upload_pdf():
    """Upload and preview PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.pdf'):
            return jsonify({'error': 'Only PDF files allowed'}), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        print(f"\n📄 Parsing PDF: {filename}")
        
        # Parse PDF
        parser = UMOATitresPDFParser(filepath)
        parsed_data = parser.parse()
        
        if len(parsed_data) == 0:
            return jsonify({'error': 'No data found in PDF'}), 400
        
        # Return preview (first 20 records)
        preview = parsed_data.head(20)
        preview_dict = preview.to_dict('records')
        
        # Serialize preview
        formatted_preview = [serialize_dict(record) for record in preview_dict]
        
        return jsonify({
            'success': True,
            'filename': filename,
            'total_records': len(parsed_data),
            'preview': formatted_preview,
            'countries': sorted(parsed_data['country_code'].unique().tolist()),
            'security_types': sorted(parsed_data['security_type'].unique().tolist()),
            'oat_count': len(parsed_data[parsed_data['security_type'] == 'OAT']),
            'bat_count': len(parsed_data[parsed_data['security_type'] == 'BAT'])
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/confirm-upload', methods=['POST'])
def confirm_upload():
    """Confirm and process uploaded PDF into database"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        uploaded_by = data.get('uploaded_by', 'admin')
        
        if not filename:
            return jsonify({'error': 'Filename required'}), 400
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        print(f"\n💾 Processing upload into database: {filename}")
        
        # Parse PDF again
        parser = UMOATitresPDFParser(filepath)
        parsed_data = parser.parse()
        
        # Process into database
        stats = db_manager.process_upload(
            parsed_data, 
            filename, 
            uploaded_by
        )
        
        # Clean up file
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"Confirm upload error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ============ STATISTICS ENDPOINTS ============

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics"""
    try:
        stats = db_manager.get_statistics()
        
        return jsonify({
            'total_securities': stats['total_securities'],
            'countries': stats['countries'],
            'oat_count': stats['oat_count'],
            'bat_count': stats['bat_count'],
            'last_update': serialize_value(stats['last_update'])
        })
        
    except Exception as e:
        print(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-history', methods=['GET'])
def get_upload_history():
    """Get recent upload history for both PDF and Excel uploads"""
    try:
        limit = request.args.get('limit', 10, type=int)

        # Get PDF upload history
        pdf_history = db_manager.get_upload_history(limit)
        formatted_pdf = [serialize_dict(h) for h in pdf_history]

        # Get Excel upload history
        excel_history = db_manager.get_excel_upload_history(limit)
        formatted_excel = [serialize_dict(h) for h in excel_history]

        return jsonify({
            'pdf': formatted_pdf,
            'excel': formatted_excel,
            'history': formatted_pdf  # Keep backwards compatibility
        })

    except Exception as e:
        print(f"Upload history error: {e}")
        return jsonify({'error': str(e)}), 500


# ============ EXCEL UPLOAD ENDPOINTS ============

@app.route('/api/upload-excel', methods=['POST'])
def upload_excel():
    """Upload and process yield curve Excel file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Check file extension
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'File must be an Excel file (.xlsx or .xls)'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save file temporarily
        file.save(filepath)

        print(f"\n📊 Parsing Excel file: {filename}")

        # Parse Excel file
        parser = YieldCurveExcelParser()
        data = parser.parse(filepath)

        if not data:
            os.remove(filepath)
            summary = parser.get_summary()
            return jsonify({
                'error': 'No data extracted from Excel',
                'warnings': summary.get('warnings', []),
                'errors': summary.get('errors', [])
            }), 400

        # Count unique countries
        countries = set(row['country_code'] for row in data)

        # Save to database
        stats = db_manager.save_yield_curves(data, filename)

        # Clean up
        os.remove(filepath)

        summary = parser.get_summary()

        return jsonify({
            'success': True,
            'filename': filename,
            'countries_parsed': len(countries),
            'total_rows': len(data),
            'inserted': stats['inserted'],
            'warnings': summary.get('warnings', []),
            'errors': stats.get('errors', [])
        })

    except Exception as e:
        print(f"Excel upload error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/yield-curve/<country_code>', methods=['GET'])
def get_yield_curve(country_code):
    """Get latest yield curve for a country"""
    try:
        curve = db_manager.get_yield_curve(country_code)

        if not curve:
            return jsonify({
                'found': False,
                'error': f'No yield curve data for {country_code}'
            }), 404

        return jsonify({
            'found': True,
            'country_code': country_code.upper(),
            'data': [serialize_dict(point) for point in curve],
            'upload_date': serialize_value(curve[0]['upload_date']) if curve else None
        })

    except Exception as e:
        print(f"Yield curve error: {e}")
        return jsonify({'error': str(e)}), 500

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ============ STARTUP ============


@app.route('/api/countries', methods=['GET'])
def get_countries():
    """Get list of all countries with bond counts"""
    cursor = None
    try:
        cursor = db_manager.conn.cursor()
        cursor.execute("""
            SELECT
                country_code,
                country_name,
                COUNT(*) as count
            FROM securities
            WHERE status = 'active'
            GROUP BY country_code, country_name
            ORDER BY country_code
        """)

        countries = []
        for row in cursor.fetchall():
            countries.append({
                'code': row[0],
                'name': row[1],
                'count': row[2]
            })

        return jsonify({
            'countries': countries,
            'total': len(countries)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()

# Run application

@app.route('/api/bonds/country/<country_code>', methods=['GET'])
def get_bonds_by_country(country_code):
    """Get all bonds for a specific country"""
    cursor = None
    try:
        cursor = db_manager.conn.cursor()
        cursor.execute("""
            SELECT * FROM securities
            WHERE country_code = %s AND status = 'active'
            ORDER BY maturity_date
        """, (country_code.upper(),))

        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in cursor.fetchall():
            bond = dict(zip(columns, row))
            results.append(serialize_dict(bond))

        # Track country search
        track_search(country_code.upper())

        return jsonify({
            'found': True,
            'count': len(results),
            'country': country_code.upper(),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()


@app.route('/api/analytics', methods=['GET'])
def get_search_analytics():
    """Get search analytics data"""
    try:
        # Get total securities count
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM securities WHERE status = 'active'")
        total_securities = cursor.fetchone()[0]
        cursor.close()

        # Sort by count descending
        country_data = sorted(
            search_analytics['by_country'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        isin_data = sorted(
            search_analytics['by_isin'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]  # Top 10 ISINs

        return jsonify({
            'total_searches': search_analytics['total_searches'],
            'total_securities': total_securities,
            'by_country': [{'country': k, 'count': v} for k, v in country_data],
            'top_isins': [{'isin': k, 'count': v} for k, v in isin_data]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/analytics/reset', methods=['POST'])
def reset_analytics():
    """Reset search analytics"""
    global search_analytics
    search_analytics = {
        'by_country': defaultdict(int),
        'by_isin': defaultdict(int),
        'total_searches': 0
    }
    return jsonify({'success': True, 'message': 'Analytics reset'})


@app.route('/api/fix-classifications', methods=['POST'])
def fix_classifications():
    """
    Fix misclassified securities based on coupon_rate rule:
    - OAT: has coupon_rate (NOT NULL)
    - BAT: no coupon_rate (NULL)
    """
    try:
        stats = db_manager.fix_security_classifications()
        return jsonify({
            'success': True,
            'message': 'Security classifications fixed',
            'stats': stats
        })
    except Exception as e:
        print(f"Classification fix error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("UMOA BOND INTELLIGENCE DASHBOARD")
    print("="*60)
    
    # Test database connection
    try:
        db_manager.connect()
        print("✓ Database connected successfully\n")
        
        # Get stats
        cursor = db_manager.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM securities WHERE status = 'active'")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT country_code) FROM securities WHERE status = 'active'")
        countries = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM securities WHERE status = 'active' AND security_type = 'OAT'")
        oat_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM securities WHERE status = 'active' AND security_type = 'BAT'")
        bat_count = cursor.fetchone()[0]
        
        print(f"📊 Database Status:")
        print(f"   Total Securities: {total}")
        print(f"   Countries: {countries}")
        print(f"   OAT Count: {oat_count}")
        print(f"   BAT Count: {bat_count}\n")
        
        print(f"✓ Server starting on http://localhost:5000")
        print(f"✓ Health check: http://localhost:5000/health\n")
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        print(f"   Please ensure PostgreSQL is running and database is created\n")
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=5000)
