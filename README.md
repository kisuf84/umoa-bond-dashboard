# UMOA Bond Intelligence Dashboard

**Decision support tool for UMOA securities brokers**

Built for Mamoudou (Courtier, Dakar) by Konate Labs

---

## What It Does

Transforms this workflow:
- ❌ **5 minutes**: Manually look up bond codes, verify existence, calculate yields
- ✅ **30 seconds**: Instant search, automatic calculations, client matching

## Features

### ✨ Core Features (MVP)
1. **Smart Bond Search** - Find bonds by shorthand (e.g., "CI 1234")
2. **Instant Verification** - Check if security exists and get full details
3. **Yield Calculator** - Calculate YTM automatically from price
4. **Monthly PDF Upload** - Simple drag-and-drop data updates

### 🚀 Future Features
- Client constraint matching (min yield, max maturity)
- Deal history tracking
- Multi-broker support
- Mobile app

---

## Project Structure

```
umoa_bond_dashboard/
├── backend/                    # Python Flask API
│   ├── app.py                 # Main Flask application
│   ├── pdf_parser.py          # Parse UMOA-Titres PDFs
│   ├── database_manager.py    # Database operations
│   ├── yield_calculator.py    # Bond yield formulas
│   ├── requirements.txt       # Python dependencies
│   └── .env.example           # Environment template
│
├── database/                   # Database files
│   └── schema.sql             # PostgreSQL schema
│
├── frontend/                   # React UI (coming soon)
│
└── docs/                       # Documentation
    ├── TESTING_GUIDE.md       # How to test everything
    └── TECHNICAL_SPEC.md      # Full technical specification
```

---

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- PDF file from UMOA-Titres

### 1. Set Up Database
```bash
# Install PostgreSQL
sudo apt install postgresql

# Create database
sudo -u postgres psql
CREATE DATABASE umoa_bonds;
\q

# Load schema
sudo -u postgres psql -d umoa_bonds -f database/schema.sql
```

### 2. Install Backend
```bash
cd backend

# Install dependencies
pip install -r requirements.txt --break-system-packages

# Configure environment
cp .env.example .env
nano .env  # Edit with your database credentials
```

### 3. Load Initial Data
```bash
# Parse and upload PDF
python3 << 'EOF'
from pdf_parser import UMOATitresPDFParser
from database_manager import SecurityDatabaseManager

# Connect to database
db = SecurityDatabaseManager({
    'host': 'localhost',
    'database': 'umoa_bonds',
    'user': 'postgres',
    'password': 'password'
})
db.connect()

# Parse PDF
parser = UMOATitresPDFParser('path/to/UT-LTV-31_12_2025.pdf')
data = parser.parse()

# Upload
db.process_upload(data, 'UT-LTV-31_12_2025.pdf', 'admin')
db.close()
EOF
```

### 4. Start Server
```bash
python3 app.py
```

Server runs at: `http://localhost:5000`

---

## API Usage

### Search for Bond
```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "CI 1234"}'
```

Response:
```json
{
  "found": true,
  "count": 1,
  "results": [{
    "isin_code": "CI0000001234",
    "country_name": "Côte d'Ivoire",
    "security_type": "OAT",
    "maturity_date": "2027-06-30",
    "coupon_rate": 0.06
  }]
}
```

### Calculate Yield
```bash
curl -X POST http://localhost:5000/api/calculate-yield \
  -H "Content-Type: application/json" \
  -d '{
    "isin": "CI0000001234",
    "price": 97.5
  }'
```

Response:
```json
{
  "isin": "CI0000001234",
  "price": 97.5,
  "yield": 6.52,
  "coupon_rate": 6.0,
  "time_to_maturity_years": 1.42
}
```

---

## Testing

See detailed testing guide: [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md)

Quick test:
```bash
# 1. Check health
curl http://localhost:5000/health

# 2. Get statistics
curl http://localhost:5000/api/stats

# 3. Search bond
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "SN 2171"}'
```

---

## Data Source

**UMOA-Titres** publishes monthly PDFs:
- URL: https://www.umoatitres.org/en/publications/
- File: "Liste des titres publics émis par voie d'adjudication en vie"
- Format: `UT-LTV-DD_MM_YYYY.pdf`
- Frequency: Monthly

---

## Technology Stack

- **Backend**: Python 3.8, Flask
- **Database**: PostgreSQL 12
- **PDF Parsing**: pdfplumber
- **Frontend**: React 18 (coming soon)
- **Deployment**: Heroku/Railway/VPS

---

## Roadmap

### Phase 1: MVP (Current)
- [x] PDF parser for UMOA format
- [x] Database schema design
- [x] Search by ISIN/shortcode
- [x] Yield calculator
- [x] REST API
- [ ] React frontend
- [ ] Basic testing

### Phase 2: Enhanced Features
- [ ] Client constraint profiles
- [ ] Bulk yield calculations
- [ ] Deal history tracking
- [ ] Excel export
- [ ] User authentication

### Phase 3: Scale
- [ ] Multi-broker support
- [ ] Mobile app
- [ ] Real-time price feeds
- [ ] Analytics dashboard
- [ ] WhatsApp/SMS integration

---

## Contributing

Built by Konate Labs for the West African bond market.

For questions or support:
- Email: issouf@konatelabs.com
- Website: konatelabs.com

---

## License

Proprietary - Konate Labs © 2026

---

## Acknowledgments

- **UMOA-Titres** for publishing monthly securities data
- **Mamoudou** for product validation and domain expertise
- **West African fixed-income community** for insights

---

**Built with ❤️ in Dakar, Senegal**
