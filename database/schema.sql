-- UMOA Bond Intelligence Dashboard
-- Database Schema
-- PostgreSQL

-- Drop existing tables (for development)
DROP TABLE IF EXISTS client_profiles CASCADE;
DROP TABLE IF EXISTS yield_curves CASCADE;
DROP TABLE IF EXISTS upload_history CASCADE;
DROP TABLE IF EXISTS securities CASCADE;

-- Main securities table
CREATE TABLE securities (
    id SERIAL PRIMARY KEY,
    
    -- Identification
    isin_code VARCHAR(20) UNIQUE NOT NULL,
    short_code VARCHAR(4) NOT NULL,
    country_code VARCHAR(2) NOT NULL,
    country_name VARCHAR(20),
    
    -- Classification
    security_type VARCHAR(3) NOT NULL CHECK (security_type IN ('OAT', 'BAT')),
    original_maturity VARCHAR(10),
    
    -- Dates
    issue_date DATE NOT NULL,
    maturity_date DATE NOT NULL,
    remaining_duration NUMERIC(5,2),
    
    -- Financial details
    coupon_rate NUMERIC(6,4),
    outstanding_amount NUMERIC(15,2),
    periodicity VARCHAR(1) DEFAULT 'A',
    amortization_mode VARCHAR(5) DEFAULT 'IF',
    deferred_years INTEGER,
    
    -- Status and metadata
    status VARCHAR(10) DEFAULT 'active' CHECK (status IN ('active', 'matured', 'redeemed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deprecated_at TIMESTAMP NULL,
    source_file VARCHAR(255),
    
    -- Indexes
    CONSTRAINT chk_maturity_future CHECK (maturity_date >= issue_date)
);

-- Create indexes for fast lookup
CREATE INDEX idx_isin ON securities(isin_code);
CREATE INDEX idx_short_code ON securities(short_code, country_code);
CREATE INDEX idx_country ON securities(country_code);
CREATE INDEX idx_type ON securities(security_type);
CREATE INDEX idx_maturity ON securities(maturity_date);
CREATE INDEX idx_status ON securities(status);

-- Upload history table
CREATE TABLE upload_history (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by VARCHAR(100),
    
    -- Statistics
    records_added INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_deprecated INTEGER DEFAULT 0,
    total_processed INTEGER DEFAULT 0,
    
    -- Status
    processing_status VARCHAR(20) CHECK (processing_status IN ('pending', 'processing', 'success', 'failed', 'partial')),
    error_log TEXT,
    processing_duration INTEGER,
    
    -- Metadata
    pdf_date DATE,
    file_size INTEGER
);

CREATE INDEX idx_upload_date ON upload_history(upload_date);
CREATE INDEX idx_processing_status ON upload_history(processing_status);

-- Yield curves table (for market rate comparison)
CREATE TABLE yield_curves (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    maturity_years DECIMAL(5,2) NOT NULL,
    zero_coupon_rate DECIMAL(8,4),
    oat_rate DECIMAL(8,4),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    excel_filename VARCHAR(255),

    CONSTRAINT unique_curve_point UNIQUE (country_code, maturity_years, upload_date)
);

CREATE INDEX idx_yield_curve_country ON yield_curves(country_code);
CREATE INDEX idx_yield_curve_date ON yield_curves(upload_date DESC);

COMMENT ON TABLE yield_curves IS 'Stores yield curve data for each UMOA country';

-- Client profiles table (for future use)
CREATE TABLE client_profiles (
    id SERIAL PRIMARY KEY,
    client_name VARCHAR(100) NOT NULL,
    min_yield NUMERIC(6,4),
    max_yield NUMERIC(6,4),
    min_maturity DATE,
    max_maturity DATE,
    preferred_countries TEXT[],
    preferred_types TEXT[],
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for securities table
CREATE TRIGGER update_securities_updated_at 
    BEFORE UPDATE ON securities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for client_profiles table
CREATE TRIGGER update_client_profiles_updated_at
    BEFORE UPDATE ON client_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing (optional)
COMMENT ON TABLE securities IS 'Stores UMOA government securities (bonds and bills)';
COMMENT ON TABLE upload_history IS 'Tracks PDF uploads and processing results';
COMMENT ON TABLE client_profiles IS 'Stores client investment constraints for matching';
