--
-- PostgreSQL database dump
--


-- Dumped from database version 14.20 (Homebrew)
-- Dumped by pg_dump version 14.20 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: client_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.client_profiles (
    id integer NOT NULL,
    client_name character varying(100) NOT NULL,
    min_yield numeric(6,4),
    max_yield numeric(6,4),
    min_maturity date,
    max_maturity date,
    preferred_countries text[],
    preferred_types text[],
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE client_profiles; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.client_profiles IS 'Stores client investment constraints for matching';


--
-- Name: client_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.client_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: client_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.client_profiles_id_seq OWNED BY public.client_profiles.id;


--
-- Name: securities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.securities (
    id integer NOT NULL,
    isin_code character varying(20) NOT NULL,
    short_code character varying(4) NOT NULL,
    country_code character varying(2) NOT NULL,
    country_name character varying(20),
    security_type character varying(3) NOT NULL,
    original_maturity character varying(10),
    issue_date date,
    maturity_date date NOT NULL,
    remaining_duration numeric(5,2),
    coupon_rate numeric(6,4),
    outstanding_amount numeric(15,2),
    periodicity character varying(1) DEFAULT 'A'::character varying,
    amortization_mode character varying(5) DEFAULT 'IF'::character varying,
    deferred_years integer,
    status character varying(10) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    deprecated_at timestamp without time zone,
    source_file character varying(255),
    CONSTRAINT chk_maturity_future CHECK ((maturity_date >= issue_date)),
    CONSTRAINT securities_security_type_check CHECK (((security_type)::text = ANY ((ARRAY['OAT'::character varying, 'BAT'::character varying])::text[]))),
    CONSTRAINT securities_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'matured'::character varying, 'redeemed'::character varying])::text[])))
);


--
-- Name: TABLE securities; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.securities IS 'Stores UMOA government securities (bonds and bills)';


--
-- Name: securities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.securities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: securities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.securities_id_seq OWNED BY public.securities.id;


--
-- Name: upload_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.upload_history (
    id integer NOT NULL,
    filename character varying(255) NOT NULL,
    upload_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    uploaded_by character varying(100),
    records_added integer DEFAULT 0,
    records_updated integer DEFAULT 0,
    records_deprecated integer DEFAULT 0,
    total_processed integer DEFAULT 0,
    processing_status character varying(20),
    error_log text,
    processing_duration integer,
    pdf_date date,
    file_size integer,
    CONSTRAINT upload_history_processing_status_check CHECK (((processing_status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'success'::character varying, 'failed'::character varying, 'partial'::character varying])::text[])))
);


--
-- Name: TABLE upload_history; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.upload_history IS 'Tracks PDF uploads and processing results';


--
-- Name: upload_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.upload_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: upload_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.upload_history_id_seq OWNED BY public.upload_history.id;


--
-- Name: yield_curves; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.yield_curves (
    id integer NOT NULL,
    country_code character varying(2) NOT NULL,
    maturity_years numeric(5,2) NOT NULL,
    zero_coupon_rate numeric(8,4),
    oat_rate numeric(8,4),
    upload_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    excel_filename character varying(255)
);


--
-- Name: TABLE yield_curves; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.yield_curves IS 'Stores yield curve data for each UMOA country';


--
-- Name: yield_curves_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.yield_curves_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: yield_curves_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.yield_curves_id_seq OWNED BY public.yield_curves.id;


--
-- Name: client_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_profiles ALTER COLUMN id SET DEFAULT nextval('public.client_profiles_id_seq'::regclass);


--
-- Name: securities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.securities ALTER COLUMN id SET DEFAULT nextval('public.securities_id_seq'::regclass);


--
-- Name: upload_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_history ALTER COLUMN id SET DEFAULT nextval('public.upload_history_id_seq'::regclass);


--
-- Name: yield_curves id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.yield_curves ALTER COLUMN id SET DEFAULT nextval('public.yield_curves_id_seq'::regclass);


--
-- Name: client_profiles client_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.client_profiles
    ADD CONSTRAINT client_profiles_pkey PRIMARY KEY (id);


--
-- Name: securities securities_isin_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.securities
    ADD CONSTRAINT securities_isin_code_key UNIQUE (isin_code);


--
-- Name: securities securities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.securities
    ADD CONSTRAINT securities_pkey PRIMARY KEY (id);


--
-- Name: yield_curves unique_curve_point; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.yield_curves
    ADD CONSTRAINT unique_curve_point UNIQUE (country_code, maturity_years, upload_date);


--
-- Name: upload_history upload_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_history
    ADD CONSTRAINT upload_history_pkey PRIMARY KEY (id);


--
-- Name: yield_curves yield_curves_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.yield_curves
    ADD CONSTRAINT yield_curves_pkey PRIMARY KEY (id);


--
-- Name: idx_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_country ON public.securities USING btree (country_code);


--
-- Name: idx_isin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_isin ON public.securities USING btree (isin_code);


--
-- Name: idx_maturity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_maturity ON public.securities USING btree (maturity_date);


--
-- Name: idx_processing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_status ON public.upload_history USING btree (processing_status);


--
-- Name: idx_short_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_short_code ON public.securities USING btree (short_code, country_code);


--
-- Name: idx_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_status ON public.securities USING btree (status);


--
-- Name: idx_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_type ON public.securities USING btree (security_type);


--
-- Name: idx_upload_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_upload_date ON public.upload_history USING btree (upload_date);


--
-- Name: idx_yield_curve_country; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_yield_curve_country ON public.yield_curves USING btree (country_code);


--
-- Name: idx_yield_curve_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_yield_curve_date ON public.yield_curves USING btree (upload_date DESC);


--
-- Name: client_profiles update_client_profiles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_client_profiles_updated_at BEFORE UPDATE ON public.client_profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: securities update_securities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_securities_updated_at BEFORE UPDATE ON public.securities FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- PostgreSQL database dump complete
--


