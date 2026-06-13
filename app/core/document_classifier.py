from enum import Enum


class DocumentType(str, Enum):
    INVOICE = "invoice"
    FINANCIAL_REPORT = "financial_report"
    LEGAL = "legal"
    TABULAR = "tabular"
    MARKDOWN = "markdown"
    NARRATIVE = "narrative"


_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.INVOICE: [
        "invoice", "bill to", "due date", "total amount", "amount due",
        "payment terms", "invoice number", "subtotal", "tax",
    ],
    DocumentType.FINANCIAL_REPORT: [
        "revenue", "profit", "balance sheet", "fiscal year", "net income",
        "earnings", "cash flow", "equity", "liabilities", "assets",
        "quarter", "annual report",
    ],
    DocumentType.LEGAL: [
        "whereas", "hereinafter", "party", "shall", "agreement",
        "contract", "clause", "jurisdiction", "indemnify", "liability",
        "representations", "warranties", "governing law",
    ],
}

_SCORE_THRESHOLD = 0.5  # minimum density (hits per 1000 words) to accept a classification


class DocumentClassifier:
    def classify(self, text: str, metadata: dict) -> DocumentType:
        # Stage 1: file_type short-circuits (highest confidence)
        file_type = metadata.get("file_type", "")
        if file_type in {"xlsx", "xls", "csv"}:
            return DocumentType.TABULAR
        if file_type == "md":
            return DocumentType.MARKDOWN

        # Stage 2: keyword density scoring
        lower = text.lower()
        word_count = max(len(text.split()), 1)
        scores: dict[DocumentType, float] = {dt: 0.0 for dt in DocumentType}

        for doc_type, keywords in _KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in lower)
            scores[doc_type] = (hits / word_count) * 1000

        # Stage 3: structural boosts
        lines = text.splitlines()
        line_count = max(len(lines), 1)

        tab_density = text.count("\t") / line_count
        pipe_density = text.count("|") / line_count
        if tab_density >= 2.0 or pipe_density > 0.5:
            scores[DocumentType.TABULAR] += 5.0

        md_line_count = sum(
            1 for ln in lines
            if ln.startswith("#") or ln.startswith("```") or ln.startswith("**") or ln.startswith("- ")
        )
        if md_line_count / line_count >= 0.05:
            scores[DocumentType.MARKDOWN] += 5.0

        # Decision
        best_type = max(scores, key=lambda dt: scores[dt])
        if scores[best_type] < _SCORE_THRESHOLD:
            return DocumentType.NARRATIVE
        return best_type
