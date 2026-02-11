-- Migration: Add yield_curves table
-- Run this to add yield curve support to existing database

-- Create yield_curves table if not exists
CREATE TABLE IF NOT EXISTS yield_curves (
    id SERIAL PRIMARY KEY,
    country_code VARCHAR(2) NOT NULL,
    maturity_years DECIMAL(5,2) NOT NULL,
    zero_coupon_rate DECIMAL(8,4),
    oat_rate DECIMAL(8,4),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    excel_filename VARCHAR(255),

    CONSTRAINT unique_curve_point UNIQUE (country_code, maturity_years, upload_date)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_yield_curve_country ON yield_curves(country_code);
CREATE INDEX IF NOT EXISTS idx_yield_curve_date ON yield_curves(upload_date DESC);

-- Add comment
COMMENT ON TABLE yield_curves IS 'Stores yield curve data for each UMOA country';

-- Verify creation
SELECT 'yield_curves table created successfully' as status;
