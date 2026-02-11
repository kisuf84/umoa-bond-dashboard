# UMOA Bond Dashboard - Testing Guide

## Phase 1: Setup & Database Testing

### Step 1: Install PostgreSQL
```bash
# For Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo service postgresql start

# Check status
sudo service postgresql status
```

### Step 2: Create Database
```bash
# Switch to postgres user
sudo -u postgres psql

# Inside PostgreSQL prompt:
CREATE DATABASE umoa_bonds;
CREATE USER umoa_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE umoa_bonds TO umoa_user;
\q
```

### Step 3: Initialize Database Schema
```bash
cd /home/claude/umoa_bond_dashboard

# Load schema
sudo -u postgres psql -d umoa_bonds -f database/schema.sql

# Verify tables were created
sudo -u postgres psql -d umoa_bonds -c "\dt"
```

Expected output:
```
              List of relations
 Schema |      Name       | Type  |  Owner
--------+-----------------+-------+----------
 public | client_profiles | table | postgres
 public | securities      | table | postgres
 public | upload_history  | table | postgres
```

---

## Phase 2: Backend Testing

### Step 1: Install Python Dependencies
```bash
cd /home/claude/umoa_bond_dashboard/backend

# Install dependencies
pip install -r requirements.txt --break-system-packages
```

### Step 2: Configure Environment
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
nano .env
```

Update these values:
```
DB_HOST=localhost
DB_NAME=umoa_bonds
DB_USER=postgres  # or umoa_user
DB_PASSWORD=your_password
```

### Step 3: Test PDF Parser
```bash
cd /home/claude/umoa_bond_dashboard/backend

# Test with the uploaded PDF
python3 pdf_parser.py /mnt/user-data/uploads/UT-LTV-31_12_2025.pdf
```

Expected output:
```
Parsing PDF: /mnt/user-data/uploads/UT-LTV-31_12_2025.pdf
  → Processing Bénin (BJ)
  → Processing Burkina Faso (BF)
  ...
Parsed 788 securities

Total securities parsed: 788
Countries: ['BJ', 'BF', 'CI', 'GW', 'ML', 'NE', 'SN', 'TG']
Security types: ['OAT', 'BAT']
```

### Step 4: Test Database Manager
```bash
# Test database connection
python3 database_manager.py
```

Expected output:
```
✓ Database connected successfully

Database Statistics:
  Total Securities: 0
  Countries: 0
  OAT Count: 0
  BAT Count: 0
✓ Database connection closed
```

### Step 5: Test Yield Calculator
```bash
# Run yield calculator tests
python3 yield_calculator.py
```

Expected output shows yield calculations for sample bonds.

### Step 6: Process PDF into Database
```bash
# Create a simple test script
cat > test_upload.py << 'EOF'
import os
from pdf_parser import UMOATitresPDFParser
from database_manager import SecurityDatabaseManager

# Database config
db_config = {
    'host': 'localhost',
    'database': 'umoa_bonds',
    'user': 'postgres',
    'password': 'password'
}

# Initialize
db = SecurityDatabaseManager(db_config)
db.connect()

# Parse PDF
parser = UMOATitresPDFParser('/mnt/user-data/uploads/UT-LTV-31_12_2025.pdf')
parsed_data = parser.parse()

print(f"\nParsed {len(parsed_data)} securities")

# Upload to database
stats = db.process_upload(parsed_data, 'UT-LTV-31_12_2025.pdf', 'test_user')

print(f"\n✓ Upload complete!")
print(f"  Added: {stats['added']}")
print(f"  Updated: {stats['updated']}")
print(f"  Errors: {len(stats['errors'])}")

# Verify
db_stats = db.get_statistics()
print(f"\n📊 Database now has {db_stats['total_securities']} securities")

db.close()
EOF

# Run the test
python3 test_upload.py
```

Expected output:
```
Parsing PDF: /mnt/user-data/uploads/UT-LTV-31_12_2025.pdf
...
Parsed 788 securities

Processing 788 securities...
  → Deprecated 0 matured securities

✓ Upload processed successfully
  → Added: 788
  → Updated: 0
  → Deprecated: 0

📊 Database now has 788 securities
```

---

## Phase 3: API Testing

### Step 1: Start Flask Server
```bash
cd /home/claude/umoa_bond_dashboard/backend

# Start server
python3 app.py
```

Expected output:
```
============================================================
UMOA BOND INTELLIGENCE DASHBOARD
============================================================

✓ Database connected successfully

📊 Database Status:
   Total Securities: 788
   Countries: 8
   OAT Count: 642
   BAT Count: 146

✓ Server starting on http://localhost:5000
✓ Health check: http://localhost:5000/health

 * Running on http://0.0.0.0:5000
```

### Step 2: Test API Endpoints

Open a new terminal and run these curl commands:

#### Test 1: Health Check
```bash
curl http://localhost:5000/health
```

Expected:
```json
{
  "status": "healthy",
  "database": "connected",
  "total_securities": 788
}
```

#### Test 2: Get Statistics
```bash
curl http://localhost:5000/api/stats
```

Expected:
```json
{
  "total_securities": 788,
  "countries": 8,
  "oat_count": 642,
  "bat_count": 146,
  "last_update": "2026-01-26T..."
}
```

#### Test 3: Search for Bond
```bash
# Search for Senegal bond
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "SN 2171", "country": "SN"}'
```

Expected:
```json
{
  "found": true,
  "count": 1,
  "results": [
    {
      "isin_code": "SN0000002171",
      "short_code": "2171",
      "country_code": "SN",
      "country_name": "Sénégal",
      "security_type": "OAT",
      "maturity_date": "2026-01-09",
      "coupon_rate": 0.051,
      ...
    }
  ]
}
```

#### Test 4: Calculate Yield
```bash
# Calculate yield for the bond we just found
curl -X POST http://localhost:5000/api/calculate-yield \
  -H "Content-Type: application/json" \
  -d '{
    "isin": "SN0000002171",
    "price": 98.5
  }'
```

Expected:
```json
{
  "isin": "SN0000002171",
  "price": 98.5,
  "yield": 5.32,
  "coupon_rate": 5.1,
  "maturity_date": "2026-01-09",
  "time_to_maturity_years": 0.04,
  ...
}
```

#### Test 5: Search Without Country (Returns Multiple)
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "1234"}'
```

This should return multiple bonds from different countries with code 1234.

---

## Phase 4: Integration Testing

### Test Complete Workflow

1. **Search for a bond** → Get ISIN
2. **Calculate yield** → Get yield percentage
3. **Verify data** → Cross-check with PDF

Example workflow:
```bash
# 1. Search
ISIN=$(curl -s -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "CI 5823"}' | jq -r '.results[0].isin_code')

echo "Found ISIN: $ISIN"

# 2. Calculate yield
curl -X POST http://localhost:5000/api/calculate-yield \
  -H "Content-Type: application/json" \
  -d "{\"isin\": \"$ISIN\", \"price\": 97.5}" | jq
```

---

## Phase 5: Error Testing

### Test Invalid Inputs

```bash
# Test 1: Invalid bond code
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "INVALID9999"}'

# Expected: {"found": false, "message": "No active securities found..."}

# Test 2: Missing ISIN
curl -X POST http://localhost:5000/api/calculate-yield \
  -H "Content-Type: application/json" \
  -d '{"price": 97.5}'

# Expected: {"error": "ISIN and price required"}

# Test 3: Non-existent ISIN
curl -X POST http://localhost:5000/api/calculate-yield \
  -H "Content-Type: application/json" \
  -d '{"isin": "XX0000009999", "price": 97.5}'

# Expected: {"error": "Bond not found"}
```

---

## Success Criteria

✅ Database created with 3 tables  
✅ PDF parser extracts 788 securities  
✅ All securities loaded into database  
✅ API server starts without errors  
✅ Health check returns status  
✅ Search finds bonds correctly  
✅ Yield calculator returns accurate results  
✅ Error handling works properly  

---

## Troubleshooting

### Issue: "psycopg2" not found
```bash
pip install psycopg2-binary --break-system-packages
```

### Issue: "pdfplumber" not found
```bash
pip install pdfplumber --break-system-packages
```

### Issue: Database connection refused
```bash
# Check PostgreSQL is running
sudo service postgresql status

# If not running
sudo service postgresql start
```

### Issue: Permission denied on database
```sql
-- Connect as postgres user
sudo -u postgres psql -d umoa_bonds

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO umoa_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO umoa_user;
```

---

## Next Steps After Testing

Once all tests pass:

1. **Build frontend** - React interface for bond search
2. **Add authentication** - Secure the API
3. **Deploy** - Host on Heroku/Railway/VPS
4. **Training** - Show Mamoudou how to use it

Let me know which test fails and I'll help debug!
