"""Read-only, parameterized access to the PostgreSQL metadata DB (docs/db.sql).

The single SQL boundary for the KPI workflow. No LLM-authored SQL ever reaches the
database: callers pass structured values, every value is bound as a parameter, and
only SELECT statements are issued.
"""
import logging
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


@dataclass
class DocumentRef:
    """A company document normalized across documents/annual_reports/financial_results."""

    source_table: str
    document_id: int
    company_id: int | None
    document_type: str | None
    title: str | None
    year: str | None
    storage_id: str | None  # documents.s3_key | annual_reports.file_name | financial_results link/xbrl
    filename: str | None  # best-effort name used to pick a parser
    extra: dict = field(default_factory=dict)


class KpiRepository:
    """SELECT-only repository over the business tables used by the KPI workflow."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- users / companies / authorization ---

    def get_user_by_email(self, email: str) -> dict | None:
        logger.info("[repo:get_user_by_email] START email=%s", email)
        sql = text(
            "SELECT id, email, full_name, role FROM users WHERE lower(email) = lower(:email) LIMIT 1"
        )
        with self._engine.connect() as conn:
            row = conn.execute(sql, {"email": email}).mappings().first()
        if row is None:
            logger.info("[repo:get_user_by_email] DONE no user for email=%s", email)
            return None
        user = dict(row)
        logger.info("[repo:get_user_by_email] DONE found user_id=%s role=%s", user.get("id"), user.get("role"))
        return user

    def list_company(self) -> list[dict]:
        sql = text(
            """
            SELECT id, symbol, company_name   FROM companies
            """
        )
        with self._engine.connect() as conn:
            df = pd.read_sql_query(sql, conn)
        matches = df.to_dict(orient="records")
        logger.info("[repo:list_company] DONE returned %d compan(ies)", len(matches))
        return matches

    def find_company(self, query: str) -> list[dict]:
        """Resolve a company by symbol or name. Tries exact symbol, then ILIKE name/symbol.

        `query` is bound as a parameter — injection-y input is treated as a literal
        and simply matches nothing.
        """
        q = (query or "").strip()
        logger.info("[repo:find_company] START query=%r", query)
        if not q:
            logger.info("[repo:find_company] DONE empty query; returning no matches")
            return []
        like = f"%{q}%"
        sql = text(
            """
            SELECT id, symbol, company_name
            FROM companies
            WHERE upper(symbol) = upper(:exact)
               OR company_name ILIKE :like
               OR symbol ILIKE :like
            ORDER BY (upper(symbol) = upper(:exact)) DESC, length(company_name)
            LIMIT 10
            """
        )
        with self._engine.connect() as conn:
            df = pd.read_sql_query(sql, conn, params={"exact": q, "like": like})
        matches = df.to_dict(orient="records")
        logger.info("[repo:find_company] DONE query=%r returned %d match(es)", q, len(matches))
        return matches

    def is_user_authorized(self, user_id: int, company_id: int) -> bool:
        """True if an (active) watchlist row links this user to this company."""
        logger.info("[repo:is_user_authorized] START user_id=%s company_id=%s", user_id, company_id)
        sql = text(
            """
            SELECT 1 FROM watchlists
            WHERE user_id = :user_id AND company_id = :company_id
              AND (status IS NULL OR status = 'active')
            LIMIT 1
            """
        )
        with self._engine.connect() as conn:
            authorized = conn.execute(sql, {"user_id": user_id, "company_id": company_id}).first() is not None
        logger.info(
            "[repo:is_user_authorized] DONE user_id=%s company_id=%s -> %s",
            user_id,
            company_id,
            authorized,
        )
        return authorized

    # --- documents ---

    def find_company_documents(self, company_id: int, symbol: str | None) -> list[DocumentRef]:
        """Collect candidate filings for a company from the three source tables.

        Storage pointers are normalized into DocumentRef.storage_id so downstream
        retrieval stays table-agnostic.
        """
        logger.info(
            "[repo:find_company_documents] START company_id=%s symbol=%s", company_id, symbol
        )
        with self._engine.connect() as conn:
            refs = self._documents(conn, company_id)
        logger.info(
            "[repo:find_company_documents] DONE found %d candidate document(s) for company_id=%s",
            len(refs),
            company_id,
        )
        return refs

    def _documents(self, conn, company_id: int) -> list[DocumentRef]:
        sql = text(
            """
            SELECT id, company_id, document_type, document_title, report_year, file_name, s3_key, source, processing_status, upload_date
            FROM documents
            WHERE company_id = :company_id AND document_type = 'analyst_report'
            ORDER BY upload_date DESC NULLS LAST, id DESC
            LIMIT 50
            """
        )
        out: list[DocumentRef] = []
        for r in conn.execute(sql, {"company_id": company_id}).mappings():
            # Diagnostic: shows whether file_name is even a column in the result
            # (code/schema issue) vs present-but-NULL (data issue).
            logger.info(
                "[repo:_documents] row id=%s keys=%s file_name=%r s3_key=%r",
                r.get("id"),
                list(r.keys()),
                r.get("file_name"),
                r.get("s3_key"),
            )
            out.append(
                DocumentRef(
                    source_table="documents",
                    document_id=r["id"],
                    company_id=r["company_id"],
                    document_type=r["document_type"],
                    title=r["document_title"],
                    year=str(r["report_year"]) if r["report_year"] is not None else None,
                    storage_id=r["s3_key"],
                    # file_name carries the real extension used to pick a parser;
                    # s3_key (e.g. "file://<id>") has none, so fall back to it.
                    filename=r.get("file_name") or r["s3_key"],
                    extra={
                        "source": r["source"],
                        "processing_status": r["processing_status"],
                    },
                )
            )
        logger.debug("[repo:_documents] %d row(s) for company_id=%s", len(out), company_id)
        return out