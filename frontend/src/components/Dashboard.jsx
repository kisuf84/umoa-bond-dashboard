import { useState, useEffect } from 'react';
import axios from 'axios';
import './Dashboard.css';

const API_URL = 'http://localhost:5000';

// Country code to flag emoji mapping
const COUNTRY_FLAGS = {
  'BJ': '🇧🇯', 'BF': '🇧🇫', 'CI': '🇨🇮', 'GW': '🇬🇼',
  'ML': '🇲🇱', 'NE': '🇳🇪', 'SN': '🇸🇳', 'TG': '🇹🇬'
};

// Pie chart colors
const CHART_COLORS = [
  '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981',
  '#f59e0b', '#ef4444', '#ec4899', '#6366f1'
];

// Format ISO date (YYYY-MM-DD) as DD/MM/YYYY (French format)
// Uses string parsing to avoid timezone issues
const formatDateFR = (dateStr) => {
  if (!dateStr) return '-';
  // Handle ISO format YYYY-MM-DD
  if (dateStr.includes('-')) {
    const parts = dateStr.split('T')[0].split('-');
    if (parts.length === 3) {
      const [year, month, day] = parts;
      return `${day}/${month}/${year}`;
    }
  }
  // Already in DD/MM/YYYY format
  if (dateStr.includes('/')) {
    return dateStr;
  }
  return dateStr;
};

// Get today's date in YYYY-MM-DD format (for date input)
const getTodayISO = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Validate price input
const validatePrice = (price) => {
  const numPrice = parseFloat(price);
  if (isNaN(numPrice) || numPrice <= 0) {
    return { valid: false, error: 'Price must be positive' };
  }
  if (numPrice > 200) {
    return { valid: false, error: 'Price cannot exceed 200%' };
  }
  return { valid: true, error: null };
};

function Dashboard() {
  // State
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [countries, setCountries] = useState([]);
  const [selectedCountry, setSelectedCountry] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);
  const [activeTab, setActiveTab] = useState('search'); // 'search' | 'analytics' | 'calculator'
  const [analytics, setAnalytics] = useState(null);

  // Yield Calculator state
  const [calcIsin, setCalcIsin] = useState('');
  const [calcPrice, setCalcPrice] = useState('');
  const [calcDate, setCalcDate] = useState(getTodayISO());
  const [priceError, setPriceError] = useState('');
  const [calcBond, setCalcBond] = useState(null);
  const [calcResult, setCalcResult] = useState(null);
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcError, setCalcError] = useState('');
  const [loadedFromSearch, setLoadedFromSearch] = useState(null); // Track if ISIN was loaded from search

  useEffect(() => {
    loadCountries();
    loadStats();
  }, []);

  const loadCountries = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/countries`);
      setCountries(response.data.countries);
    } catch (err) {
      console.error('Error loading countries:', err);
    }
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/health`);
      setStats(response.data);
    } catch (err) {
      console.error('Error loading stats:', err);
    }
  };

  const loadAnalytics = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/analytics`);
      setAnalytics(response.data);
    } catch (err) {
      console.error('Error loading analytics:', err);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');
    setResults([]);
    setSelectedCountry(null);

    try {
      const response = await axios.post(`${API_URL}/api/search`, { query });
      if (response.data.results) {
        setResults(response.data.results);
      } else {
        setError(response.data.message || 'No results found');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Search failed. Use format: BF0000001792 or BF1792');
    } finally {
      setLoading(false);
    }
  };

  const handleCountryClick = async (countryCode) => {
    setLoading(true);
    setError('');
    setResults([]);
    setQuery('');
    setSelectedCountry(countryCode);

    try {
      const response = await axios.get(`${API_URL}/api/bonds/country/${countryCode}`);
      if (response.data.results) {
        setResults(response.data.results);
      } else {
        setError(`No bonds found for ${countryCode}`);
      }
    } catch (err) {
      setError('Failed to load country bonds.');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResults([]);
    setSelectedCountry(null);
    setError('');
  };

  // Yield Calculator functions
  const handleIsinLookup = async (isin) => {
    if (isin.length < 6) {
      setCalcBond(null);
      return;
    }

    try {
      const response = await axios.get(`${API_URL}/api/bond/${isin}`);
      if (response.data.found) {
        setCalcBond(response.data.bond);
        setCalcError('');
      } else {
        setCalcBond(null);
      }
    } catch (err) {
      setCalcBond(null);
    }
  };

  const handleCalculateYield = async (e) => {
    e.preventDefault();
    if (!calcIsin || !calcPrice) {
      setCalcError('ISIN and Price are required');
      return;
    }

    setCalcLoading(true);
    setCalcError('');
    setCalcResult(null);

    // Validate price
    const priceValidation = validatePrice(calcPrice);
    if (!priceValidation.valid) {
      setPriceError(priceValidation.error);
      setCalcLoading(false);
      return;
    }
    setPriceError('');

    try {
      // Ensure price is a clean number (not tuple/array/object)
      let priceValue = calcPrice;
      if (Array.isArray(priceValue)) {
        priceValue = priceValue[0];
      } else if (typeof priceValue === 'object' && priceValue !== null) {
        priceValue = Object.values(priceValue)[0];
      }
      const cleanPrice = parseFloat(String(priceValue).trim());

      console.log('Sending to API:', { isin: calcIsin, price: cleanPrice, settlement_date: calcDate });

      const response = await axios.post(`${API_URL}/api/calculate-yield`, {
        isin: calcIsin,
        price: cleanPrice,
        settlement_date: calcDate
      });
      setCalcResult(response.data);
    } catch (err) {
      setCalcError(err.response?.data?.error || 'Calculation failed');
    } finally {
      setCalcLoading(false);
    }
  };

  const handleClearCalculator = () => {
    setCalcIsin('');
    setCalcPrice('');
    setCalcDate(new Date().toISOString().split('T')[0]);
    setCalcBond(null);
    setCalcResult(null);
    setCalcError('');
    setLoadedFromSearch(null);
  };

  // Quick calculate from search results
  const handleQuickCalculate = (bond) => {
    // Set ISIN and trigger lookup
    setCalcIsin(bond.isin_code);
    setCalcBond(bond);
    setCalcPrice('');
    setCalcDate(getTodayISO());
    setCalcResult(null);
    setCalcError('');
    setLoadedFromSearch(bond.isin_code);

    // Switch to calculator tab
    setActiveTab('calculator');

    // Focus on price input after a short delay
    setTimeout(() => {
      const priceInput = document.querySelector('input[placeholder="e.g., 95.60"]');
      if (priceInput) priceInput.focus();
    }, 100);
  };

  // Calculate total bonds for display
  const totalBonds = stats?.total_securities || countries.reduce((sum, c) => sum + c.count, 0);

  // Render pie chart SVG
  const renderPieChart = (data) => {
    if (!data || data.length === 0) return null;

    const total = data.reduce((sum, d) => sum + d.count, 0);
    let currentAngle = 0;

    const slices = data.map((item, index) => {
      const percentage = item.count / total;
      const angle = percentage * 360;
      const startAngle = currentAngle;
      currentAngle += angle;

      const startRad = (startAngle - 90) * Math.PI / 180;
      const endRad = (currentAngle - 90) * Math.PI / 180;

      const x1 = 100 + 80 * Math.cos(startRad);
      const y1 = 100 + 80 * Math.sin(startRad);
      const x2 = 100 + 80 * Math.cos(endRad);
      const y2 = 100 + 80 * Math.sin(endRad);

      const largeArc = angle > 180 ? 1 : 0;

      const pathD = angle >= 360
        ? `M 100 20 A 80 80 0 1 1 99.99 20 A 80 80 0 1 1 100 20`
        : `M 100 100 L ${x1} ${y1} A 80 80 0 ${largeArc} 1 ${x2} ${y2} Z`;

      return (
        <path
          key={item.country}
          d={pathD}
          fill={CHART_COLORS[index % CHART_COLORS.length]}
          stroke="white"
          strokeWidth="2"
        />
      );
    });

    return (
      <svg viewBox="0 0 200 200" className="pie-chart">
        {slices}
      </svg>
    );
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="header">
        <div className="header-left">
          <img src="/logo.png" alt="UMOA" className="header-logo" />
          <h1>UMOA Bond Intelligence</h1>
        </div>
        <div className="header-right">
          {stats && (
            <div className="stats">
              <span className="stat-badge">📊 {stats.total_securities} Securities</span>
              <span className="stat-badge success">✅ Connected</span>
            </div>
          )}
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="tabs">
        <button
          className={`tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          🔍 Search
        </button>
        <button
          className={`tab ${activeTab === 'calculator' ? 'active' : ''}`}
          onClick={() => setActiveTab('calculator')}
        >
          📈 Yield Calculator
        </button>
        <button
          className={`tab ${activeTab === 'analytics' ? 'active' : ''}`}
          onClick={() => { setActiveTab('analytics'); loadAnalytics(); }}
        >
          📊 Analytics
        </button>
      </nav>

      {/* Search Tab */}
      {activeTab === 'search' && (
        <>
          <div className="search-section">
            <form onSubmit={handleSearch}>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter ISIN (e.g., BF0000001792 or BF1792)"
                className="search-input"
              />
              <button type="submit" disabled={loading} className="search-button">
                {loading ? '⏳' : '🔍'} Search
              </button>
              {(query || results.length > 0 || selectedCountry) && (
                <button type="button" onClick={handleClear} className="clear-button">
                  ✕ Clear
                </button>
              )}
            </form>
          </div>

          {error && <div className="error">{error}</div>}

          <div className="content">
            <aside className="sidebar">
              <h3>🌍 Countries</h3>
              <div className="country-list">
                {countries.map((country) => (
                  <div
                    key={country.code}
                    className={`country-item ${selectedCountry === country.code ? 'selected' : ''}`}
                    onClick={() => handleCountryClick(country.code)}
                  >
                    <span className="country-flag">{COUNTRY_FLAGS[country.code] || '🏳️'}</span>
                    <span className="country-code">{country.code}</span>
                    <span className="country-name">{country.name}</span>
                    <span className="country-count">{country.count}</span>
                  </div>
                ))}
              </div>
            </aside>

            <main className="results">
              {results.length > 0 ? (
                <>
                  <div className="results-header">
                    <h2>
                      {selectedCountry
                        ? `${COUNTRY_FLAGS[selectedCountry] || ''} ${countries.find(c => c.code === selectedCountry)?.name}`
                        : 'Search Results'
                      }
                    </h2>
                    <span className="results-count">
                      Showing {results.length} of {totalBonds} bonds
                    </span>
                  </div>
                  <div className="table-container">
                    <table>
                      <thead>
                        <tr>
                          <th>ISIN</th>
                          <th>Type</th>
                          <th>Country</th>
                          <th>Issue Date</th>
                          <th>Maturity</th>
                          <th>Duration</th>
                          <th>Coupon</th>
                          <th>Status</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((bond) => (
                          <tr key={bond.isin_code}>
                            <td className="isin">{bond.isin_code}</td>
                            <td>
                              <span className={`bond-type ${bond.security_type?.toLowerCase()}`}>
                                {bond.security_type}
                              </span>
                            </td>
                            <td>{COUNTRY_FLAGS[bond.country_code]} {bond.country_code}</td>
                            <td>{formatDateFR(bond.issue_date)}</td>
                            <td>{formatDateFR(bond.maturity_date)}</td>
                            <td>{bond.remaining_duration ? `${bond.remaining_duration}y` : '-'}</td>
                            <td>{bond.coupon_rate ? `${bond.coupon_rate}%` : '-'}</td>
                            <td>
                              <span className={`status ${bond.status}`}>
                                {bond.status}
                              </span>
                            </td>
                            <td>
                              <button
                                className="quick-calc-btn"
                                onClick={() => handleQuickCalculate(bond)}
                                title="Calculate yield for this bond"
                              >
                                📊 Calculate
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon">🔍</div>
                  <h2>Search UMOA Bonds</h2>
                  <p>Enter an ISIN code or select a country to browse bonds</p>
                  <div className="empty-hint">
                    <span>Format: <code>BF0000001792</code> or <code>BF1792</code></span>
                  </div>
                </div>
              )}
            </main>
          </div>
        </>
      )}

      {/* Yield Calculator Tab */}
      {activeTab === 'calculator' && (
        <div className="calculator-section">
          <div className="calculator-container">
            <div className="calculator-form-panel">
              <h2>📈 Bond Yield Calculator</h2>
              <p className="calculator-subtitle">Calculate yield to maturity for UMOA government bonds</p>

              {loadedFromSearch && (
                <div className="loaded-from-search">
                  ✓ Loaded from search: <strong>{loadedFromSearch}</strong>
                  <button
                    type="button"
                    className="dismiss-btn"
                    onClick={() => setLoadedFromSearch(null)}
                  >×</button>
                </div>
              )}

              <form onSubmit={handleCalculateYield} className="calculator-form">
                <div className="form-group">
                  <label>ISIN Code</label>
                  <input
                    type="text"
                    value={calcIsin}
                    onChange={(e) => {
                      const val = e.target.value.toUpperCase();
                      setCalcIsin(val);
                      handleIsinLookup(val);
                      setLoadedFromSearch(null); // Clear when manually editing
                    }}
                    placeholder="e.g., CI0000005823"
                    className="form-input"
                  />
                  {calcBond && (
                    <div className="bond-preview">
                      <span className="preview-label">Found:</span>
                      <span className={`bond-type ${calcBond.security_type?.toLowerCase()}`}>
                        {calcBond.security_type}
                      </span>
                      <span>{calcBond.country_name}</span>
                      <span>Coupon: {calcBond.coupon_rate ? `${calcBond.coupon_rate}%` : 'N/A'}</span>
                      <span>Maturity: {formatDateFR(calcBond.maturity_date)}</span>
                    </div>
                  )}
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Settlement Date</label>
                    <input
                      type="date"
                      value={calcDate}
                      onChange={(e) => setCalcDate(e.target.value)}
                      className="form-input"
                    />
                    <span className="form-hint">Select trade settlement date</span>
                  </div>
                  <div className="form-group">
                    <label>Price (%)</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max="200"
                      value={calcPrice}
                      onChange={(e) => {
                        setCalcPrice(e.target.value);
                        setPriceError('');
                      }}
                      placeholder="e.g., 95.60"
                      className={`form-input ${priceError ? 'input-error' : ''}`}
                    />
                    <span className="form-hint">Typically between 80% and 120%</span>
                    {priceError && <span className="field-error">{priceError}</span>}
                  </div>
                </div>

                {calcError && <div className="calc-error">{calcError}</div>}

                <div className="form-actions">
                  <button type="submit" disabled={calcLoading} className="calc-button primary">
                    {calcLoading ? '⏳ Calculating...' : '📊 Calculate Yield'}
                  </button>
                  <button type="button" onClick={handleClearCalculator} className="calc-button secondary">
                    Clear
                  </button>
                </div>
              </form>
            </div>

            <div className="calculator-results-panel">
              {calcResult ? (
                <>
                <div className="calc-results">
                  <h3>Calculation Results</h3>
                  <div className="result-card highlight">
                    <span className="result-label">{calcResult.yield_type || 'Yield to Maturity'}</span>
                    <span className="result-value large">{calcResult.yield?.toFixed(2)}%</span>
                  </div>
                  <div className="results-grid">
                    <div className="result-card">
                      <span className="result-label">Days to Maturity</span>
                      <span className="result-value">{calcResult.days_to_maturity}</span>
                    </div>
                    <div className="result-card">
                      <span className="result-label">Years to Maturity</span>
                      <span className="result-value">{calcResult.time_to_maturity_years}</span>
                    </div>
                    <div className="result-card">
                      <span className="result-label">Accrued Interest</span>
                      <span className="result-value">{calcResult.accrued_interest?.toFixed(4)}%</span>
                    </div>
                    <div className="result-card">
                      <span className="result-label">Coupon Rate</span>
                      <span className="result-value">{calcResult.coupon_rate?.toFixed(2)}%</span>
                    </div>
                  </div>
                  <div className="result-details">
                    <div className="detail-row">
                      <span>ISIN</span>
                      <span className="isin">{calcResult.isin}</span>
                    </div>
                    <div className="detail-row">
                      <span>Security Type</span>
                      <span className={`bond-type ${calcResult.security_type?.toLowerCase()}`}>
                        {calcResult.security_type}
                      </span>
                    </div>
                    <div className="detail-row">
                      <span>Country</span>
                      <span>{calcResult.country}</span>
                    </div>
                    <div className="detail-row">
                      <span>Settlement Date</span>
                      <span>{formatDateFR(calcResult.settlement_date)}</span>
                    </div>
                    <div className="detail-row">
                      <span>Maturity Date</span>
                      <span>{formatDateFR(calcResult.maturity_date)}</span>
                    </div>
                    <div className="detail-row">
                      <span>Price</span>
                      <span>{calcResult.price?.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>

                {calcResult.market_comparison && (
                  <div className="market-comparison-section">
                    <h3>📊 Market Comparison</h3>
                    <div className="comparison-grid">
                      <div className="comparison-item your-yield">
                        <label>Your Yield</label>
                        <span className="value">{calcResult.yield?.toFixed(2)}%</span>
                      </div>
                      <div className="comparison-vs">vs</div>
                      <div className="comparison-item market-rate">
                        <label>Market Rate</label>
                        <span className="value">{calcResult.market_comparison.market_rate?.toFixed(2)}%</span>
                      </div>
                    </div>
                    <div className={`spread-indicator spread-${calcResult.market_comparison.rating}`}>
                      <span className="spread-value">
                        {calcResult.market_comparison.spread > 0 ? '+' : ''}{calcResult.market_comparison.spread?.toFixed(2)}%
                      </span>
                      <span className="spread-text">{calcResult.market_comparison.spread_text}</span>
                    </div>
                    <div className={`recommendation recommendation-${calcResult.market_comparison.rating}`}>
                      {calcResult.market_comparison.recommendation}
                    </div>
                    {calcResult.market_comparison.yield_curve_date && (
                      <div className="curve-date">
                        Yield curve data: {formatDateFR(calcResult.market_comparison.yield_curve_date)}
                      </div>
                    )}
                  </div>
                )}
                </>
              ) : (
                <div className="calc-empty">
                  <div className="empty-icon">📈</div>
                  <h3>Enter Bond Details</h3>
                  <p>Fill in the ISIN and price to calculate yield</p>
                  <div className="calc-info">
                    <h4>Calculation Method</h4>
                    <ul>
                      <li><strong>OAT Bonds:</strong> Yield to Maturity (YTM)</li>
                      <li><strong>BAT Bonds:</strong> Discount Yield</li>
                      <li><strong>Day Count:</strong> Actual/365</li>
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Analytics Tab */}
      {activeTab === 'analytics' && (
        <div className="analytics-section">
          <div className="analytics-header">
            <h2>📊 Search Analytics Dashboard</h2>
            <span className="total-searches">
              Total Searches: {analytics?.total_searches || 0}
            </span>
          </div>

          <div className="analytics-grid analytics-centered">
            <div className="analytics-card analytics-card-wide">
              <h3>Search Distribution by Country</h3>
              {analytics?.by_country?.length > 0 ? (
                <div className="chart-container chart-container-centered">
                  {renderPieChart(analytics.by_country)}
                  <div className="chart-legend">
                    {analytics.by_country.map((item, index) => (
                      <div key={item.country} className="legend-item">
                        <span
                          className="legend-color"
                          style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                        />
                        <span className="legend-label">
                          {COUNTRY_FLAGS[item.country]} {item.country}
                        </span>
                        <span className="legend-value">{item.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="no-data">No search data yet</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
