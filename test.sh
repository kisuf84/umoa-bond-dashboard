#!/bin/bash

# UMOA Bond Dashboard - Quick Test Script
# This script tests all components step-by-step

echo "=========================================="
echo "UMOA BOND DASHBOARD - TESTING"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if PostgreSQL is running
echo -e "${YELLOW}[1/5] Checking PostgreSQL...${NC}"
if sudo service postgresql status > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    echo "Start it with: sudo service postgresql start"
    exit 1
fi

# Check if database exists
echo -e "\n${YELLOW}[2/5] Checking database...${NC}"
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw umoa_bonds; then
    echo -e "${GREEN}✓ Database 'umoa_bonds' exists${NC}"
else
    echo -e "${YELLOW}! Database 'umoa_bonds' not found${NC}"
    echo "Creating database..."
    sudo -u postgres psql -c "CREATE DATABASE umoa_bonds;"
    sudo -u postgres psql -d umoa_bonds -f /mnt/user-data/outputs/umoa_bond_dashboard/database/schema.sql
    echo -e "${GREEN}✓ Database created${NC}"
fi

# Check Python dependencies
echo -e "\n${YELLOW}[3/5] Checking Python dependencies...${NC}"
if python3 -c "import flask, psycopg2, pdfplumber, pandas" 2>/dev/null; then
    echo -e "${GREEN}✓ All dependencies installed${NC}"
else
    echo -e "${YELLOW}! Installing dependencies...${NC}"
    cd /mnt/user-data/outputs/umoa_bond_dashboard/backend
    pip install -r requirements.txt --break-system-packages --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
fi

# Test PDF parser
echo -e "\n${YELLOW}[4/5] Testing PDF parser...${NC}"
cd /mnt/user-data/outputs/umoa_bond_dashboard/backend
PARSE_OUTPUT=$(python3 pdf_parser.py /mnt/user-data/uploads/UT-LTV-31_12_2025.pdf 2>&1 | tail -5)
if echo "$PARSE_OUTPUT" | grep -q "Total securities parsed"; then
    echo -e "${GREEN}✓ PDF parser works${NC}"
    echo "  $PARSE_OUTPUT" | head -1
else
    echo -e "${RED}✗ PDF parser failed${NC}"
    echo "$PARSE_OUTPUT"
    exit 1
fi

# Load data into database
echo -e "\n${YELLOW}[5/5] Loading data into database...${NC}"
python3 << 'EOF'
import sys
sys.path.append('/mnt/user-data/outputs/umoa_bond_dashboard/backend')

from pdf_parser import UMOATitresPDFParser
from database_manager import SecurityDatabaseManager

try:
    # Connect
    db = SecurityDatabaseManager({
        'host': 'localhost',
        'database': 'umoa_bonds',
        'user': 'postgres',
        'password': 'password'
    })
    db.connect()
    
    # Check if already loaded
    stats = db.get_statistics()
    if stats['total_securities'] > 0:
        print(f"Database already has {stats['total_securities']} securities")
    else:
        # Parse and load
        parser = UMOATitresPDFParser('/mnt/user-data/uploads/UT-LTV-31_12_2025.pdf')
        data = parser.parse()
        
        # Upload
        upload_stats = db.process_upload(data, 'UT-LTV-31_12_2025.pdf', 'test')
        print(f"Loaded {upload_stats['added']} securities")
    
    db.close()
    sys.exit(0)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Data loaded successfully${NC}"
else
    echo -e "${RED}✗ Data load failed${NC}"
    exit 1
fi

# Success summary
echo -e "\n${GREEN}=========================================="
echo "✓ ALL TESTS PASSED!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Start the API server:"
echo "   cd /mnt/user-data/outputs/umoa_bond_dashboard/backend"
echo "   python3 app.py"
echo ""
echo "2. Test the API (in another terminal):"
echo "   curl http://localhost:5000/health"
echo "   curl http://localhost:5000/api/stats"
echo ""
echo "3. Search for a bond:"
echo "   curl -X POST http://localhost:5000/api/search \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"query\": \"SN 2171\"}'"
echo ""
