-- DROP SCHEMA public;

CREATE SCHEMA public AUTHORIZATION pg_database_owner;

COMMENT ON SCHEMA public IS 'standard public schema';

-- DROP SEQUENCE public.analyst_reports_id_seq;

CREATE SEQUENCE public.analyst_reports_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.analyst_reports_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.analyst_reports_id_seq TO postgres;

-- DROP SEQUENCE public.annual_reports_id_seq;

CREATE SEQUENCE public.annual_reports_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.annual_reports_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.annual_reports_id_seq TO postgres;

-- DROP SEQUENCE public.chunks_id_seq;

CREATE SEQUENCE public.chunks_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.chunks_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.chunks_id_seq TO postgres;

-- DROP SEQUENCE public.companies_id_seq;

CREATE SEQUENCE public.companies_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.companies_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.companies_id_seq TO postgres;

-- DROP SEQUENCE public.documents_id_seq;

CREATE SEQUENCE public.documents_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.documents_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.documents_id_seq TO postgres;

-- DROP SEQUENCE public.financial_results_id_seq;

CREATE SEQUENCE public.financial_results_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.financial_results_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.financial_results_id_seq TO postgres;

-- DROP SEQUENCE public.integrated_results_id_seq;

CREATE SEQUENCE public.integrated_results_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.integrated_results_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.integrated_results_id_seq TO postgres;

-- DROP SEQUENCE public.nsc_announcements_id_seq;

CREATE SEQUENCE public.nsc_announcements_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.nsc_announcements_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.nsc_announcements_id_seq TO postgres;

-- DROP SEQUENCE public.update_logs_id_seq;

CREATE SEQUENCE public.update_logs_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.update_logs_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.update_logs_id_seq TO postgres;

-- DROP SEQUENCE public.users_id_seq;

CREATE SEQUENCE public.users_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.users_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.users_id_seq TO postgres;

-- DROP SEQUENCE public.watchlists_id_seq;

CREATE SEQUENCE public.watchlists_id_seq
	INCREMENT BY 1
	MINVALUE 1
	MAXVALUE 9223372036854775807
	START 1
	CACHE 1
	NO CYCLE;

-- Permissions

ALTER SEQUENCE public.watchlists_id_seq OWNER TO postgres;
GRANT ALL ON SEQUENCE public.watchlists_id_seq TO postgres;
-- public.companies definition

-- Drop table

-- DROP TABLE public.companies;

CREATE TABLE public.companies ( id bigserial NOT NULL, symbol varchar NULL, company_name varchar NULL, sector varchar NULL, is_active bool NULL, created_at timestamp NULL, CONSTRAINT companies_pkey PRIMARY KEY (id), CONSTRAINT companies_symbol_key UNIQUE (symbol));

-- Permissions

ALTER TABLE public.companies OWNER TO postgres;
GRANT ALL ON TABLE public.companies TO postgres;


-- public.financial_results definition

-- Drop table

-- DROP TABLE public.financial_results;

CREATE TABLE public.financial_results ( id bigserial NOT NULL, seq_number varchar NULL, symbol varchar NULL, company_name varchar NULL, isin varchar NULL, audited varchar NULL, bank varchar NULL, consolidated varchar NULL, cumulative varchar NULL, "period" varchar NULL, relating_to varchar NULL, financial_year varchar NULL, from_date varchar NULL, to_date varchar NULL, format varchar NULL, ind_as varchar NULL, industry varchar NULL, old_new_flag varchar NULL, re_ind varchar NULL, params varchar NULL, broadcast_date varchar NULL, filing_date varchar NULL, exchdisstime varchar NULL, difference varchar NULL, result_description varchar NULL, result_detailed_data_link varchar NULL, xbrl varchar NULL, created_at timestamp NULL, CONSTRAINT financial_results_pkey PRIMARY KEY (id), CONSTRAINT financial_results_seq_number_key UNIQUE (seq_number));

-- Permissions

ALTER TABLE public.financial_results OWNER TO postgres;
GRANT ALL ON TABLE public.financial_results TO postgres;


-- public.integrated_results definition

-- Drop table

-- DROP TABLE public.integrated_results;

CREATE TABLE public.integrated_results ( id bigserial NOT NULL, seq_id varchar NULL, symbol varchar NULL, cm_name varchar NULL, sm_name varchar NULL, audited varchar NULL, consolidated varchar NULL, "type" varchar NULL, type_sub varchar NULL, qe_date varchar NULL, broadcast_date varchar NULL, creation_date varchar NULL, revised_date varchar NULL, revision_remark varchar NULL, diff varchar NULL, ixbrl varchar NULL, ixbrl_file_size varchar NULL, xbrl varchar NULL, xbrl_file_size varchar NULL, pdf_attach varchar NULL, att_file_size varchar NULL, created_at timestamp NULL, CONSTRAINT integrated_results_pkey PRIMARY KEY (id), CONSTRAINT integrated_results_seq_id_key UNIQUE (seq_id));

-- Permissions

ALTER TABLE public.integrated_results OWNER TO postgres;
GRANT ALL ON TABLE public.integrated_results TO postgres;


-- public.nsc_announcements definition

-- Drop table

-- DROP TABLE public.nsc_announcements;

CREATE TABLE public.nsc_announcements ( id bigserial NOT NULL, seq_id varchar NULL, symbol varchar NULL, sm_name varchar NULL, sm_isin varchar NULL, sm_industry varchar NULL, description varchar NULL, attchmnt_text varchar NULL, attchmnt_file varchar NULL, att_file_size varchar NULL, file_size varchar NULL, has_xbrl bool NULL, an_dt varchar NULL, exchdisstime varchar NULL, dt varchar NULL, sort_date varchar NULL, difference varchar NULL, bflag varchar NULL, csv_name varchar NULL, old_new varchar NULL, orgid varchar NULL, created_at timestamp NULL, CONSTRAINT nsc_announcements_pkey PRIMARY KEY (id), CONSTRAINT nsc_announcements_seq_id_key UNIQUE (seq_id));

-- Permissions

ALTER TABLE public.nsc_announcements OWNER TO postgres;
GRANT ALL ON TABLE public.nsc_announcements TO postgres;


-- public.users definition

-- Drop table

-- DROP TABLE public.users;

CREATE TABLE public.users ( id bigserial NOT NULL, email varchar NULL, password_hash varchar NULL, full_name varchar NULL, "role" varchar NULL, created_at timestamp NULL, CONSTRAINT ck_users_role CHECK (((role)::text = ANY ((ARRAY['analyst'::character varying, 'admin'::character varying])::text[]))), CONSTRAINT users_email_key UNIQUE (email), CONSTRAINT users_pkey PRIMARY KEY (id));

-- Permissions

ALTER TABLE public.users OWNER TO postgres;
GRANT ALL ON TABLE public.users TO postgres;


-- public.analyst_reports definition

-- Drop table

-- DROP TABLE public.analyst_reports;

CREATE TABLE public.analyst_reports ( id bigserial NOT NULL, company_id int8 NULL, broker_name varchar NULL, report_date date NULL, s3_key varchar NULL, sentiment_score float8 NULL, CONSTRAINT analyst_reports_pkey PRIMARY KEY (id), CONSTRAINT ck_analyst_reports_sentiment_score CHECK (((sentiment_score >= (0.0)::double precision) AND (sentiment_score <= (1.0)::double precision))), CONSTRAINT analyst_reports_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.analyst_reports OWNER TO postgres;
GRANT ALL ON TABLE public.analyst_reports TO postgres;


-- public.annual_reports definition

-- Drop table

-- DROP TABLE public.annual_reports;

CREATE TABLE public.annual_reports ( id bigserial NOT NULL, company_id int8 NULL, symbol varchar NULL, company_name varchar NULL, from_yr varchar NULL, to_yr varchar NULL, submission_type varchar NULL, broadcast_dttm varchar NULL, dissemination_date_time varchar NULL, time_taken varchar NULL, file_name varchar NULL, att_file_size varchar NULL, created_at timestamp NULL, CONSTRAINT annual_reports_file_name_key UNIQUE (file_name), CONSTRAINT annual_reports_pkey PRIMARY KEY (id), CONSTRAINT annual_reports_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.annual_reports OWNER TO postgres;
GRANT ALL ON TABLE public.annual_reports TO postgres;


-- public.documents definition

-- Drop table

-- DROP TABLE public.documents;

CREATE TABLE public.documents ( id bigserial NOT NULL, company_id int8 NULL, document_type varchar NULL, document_title varchar NULL, report_year varchar NULL, s3_key varchar NULL, "source" varchar NULL, upload_date timestamp NULL, processing_status varchar NULL, CONSTRAINT documents_pkey PRIMARY KEY (id), CONSTRAINT documents_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.documents OWNER TO postgres;
GRANT ALL ON TABLE public.documents TO postgres;


-- public.update_logs definition

-- Drop table

-- DROP TABLE public.update_logs;

CREATE TABLE public.update_logs ( id bigserial NOT NULL, company_id int8 NULL, update_type varchar NULL, status varchar NULL, message varchar NULL, created_at timestamp NULL, CONSTRAINT ck_update_logs_status CHECK (((status)::text = ANY ((ARRAY['success'::character varying, 'failed'::character varying, 'skipped'::character varying])::text[]))), CONSTRAINT ck_update_logs_type CHECK (((update_type)::text = ANY ((ARRAY['mcp_refresh'::character varying, 'rag_process'::character varying, 'manual'::character varying])::text[]))), CONSTRAINT update_logs_pkey PRIMARY KEY (id), CONSTRAINT update_logs_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.update_logs OWNER TO postgres;
GRANT ALL ON TABLE public.update_logs TO postgres;


-- public.watchlists definition

-- Drop table

-- DROP TABLE public.watchlists;

CREATE TABLE public.watchlists ( id bigserial NOT NULL, user_id int8 NULL, company_id int8 NULL, frequency varchar NULL, last_checked timestamp NULL, status varchar NULL, CONSTRAINT ck_watchlists_frequency CHECK (((frequency)::text = ANY ((ARRAY['daily'::character varying, 'weekly'::character varying])::text[]))), CONSTRAINT ck_watchlists_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'paused'::character varying])::text[]))), CONSTRAINT watchlists_pkey PRIMARY KEY (id), CONSTRAINT watchlists_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE, CONSTRAINT watchlists_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.watchlists OWNER TO postgres;
GRANT ALL ON TABLE public.watchlists TO postgres;


-- public.chunks definition

-- Drop table

-- DROP TABLE public.chunks;

CREATE TABLE public.chunks ( id bigserial NOT NULL, document_id int8 NULL, pinecone_namespace varchar NULL, chunk_count int4 NULL, CONSTRAINT chunks_pkey PRIMARY KEY (id), CONSTRAINT chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE);

-- Permissions

ALTER TABLE public.chunks OWNER TO postgres;
GRANT ALL ON TABLE public.chunks TO postgres;




-- Permissions

GRANT ALL ON SCHEMA public TO pg_database_owner;
GRANT USAGE ON SCHEMA public TO public;