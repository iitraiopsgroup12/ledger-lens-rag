"""`KpiRegistry` — the allow-list of KPI categories the workflow may compute.

Parsed from the KPI catalog markdown (docs/KPI-List.txt). The registry is the
single source of truth for which KPIs exist; the LLM is constrained to this set
when generating the final KPI JSON.
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# "## 1. Revenue & Growth KPIs"  -> category title
_CATEGORY_RE = re.compile(r"^##\s*\d+\.\s*(.+?)\s*$")
# "26. Gross Profit"             -> KPI name
_KPI_RE = re.compile(r"^\d+\.\s*(.+?)\s*$")
# token splitter used for fuzzy category matching against a free-text request
_NORMALIZE_RE = re.compile(r"[^a-z]+")

# Words that carry no discriminating signal when matching a category by name.
_STOPWORDS = {"kpis", "kpi", "ratios", "ratio", "and", "sector", "advanced", "the"}


class KpiRegistry:
    """Parsed KPI catalog: ordered categories, each with its list of KPI names."""

    def __init__(self, categories: dict[str, list[str]]) -> None:
        self.categories = categories

    @classmethod
    def from_files(cls, kpi_list_path: str, kpi_prompt_path: str | None = None) -> "KpiRegistry":
        """Build the registry by parsing the KPI catalog markdown.

        `kpi_prompt_path` is accepted for symmetry with the prompt template the
        nodes load separately; only the KPI list is parsed here.
        """
        content = Path(kpi_list_path).read_text(encoding="utf-8")
        categories: dict[str, list[str]] = {}
        current: str | None = None
        for line in content.splitlines():
            cat = _CATEGORY_RE.match(line)
            if cat:
                current = cat.group(1).strip()
                categories.setdefault(current, [])
                continue
            if current is None:
                continue
            kpi = _KPI_RE.match(line)
            if kpi:
                categories[current].append(kpi.group(1).strip())
        total = sum(len(v) for v in categories.values())
        logger.info(
            "Loaded KPI registry from %s — %d categories, %d KPIs",
            kpi_list_path,
            len(categories),
            total,
        )
        return cls(categories)

    def _tokens(self, text: str) -> set[str]:
        return {t for t in _NORMALIZE_RE.split((text or "").lower()) if t and t not in _STOPWORDS}

    def match_categories(self, message: str) -> dict[str, list[str]]:
        """Return the subset of categories whose name overlaps the request.

        A category matches when any meaningful token from its title appears in
        the message (e.g. "profitability" -> "Profitability KPIs"). Returns an
        empty dict when nothing matches; callers fall back to the full registry.
        """
        msg_tokens = self._tokens(message)
        matched: dict[str, list[str]] = {}
        for name, kpis in self.categories.items():
            if self._tokens(name) & msg_tokens:
                matched[name] = kpis
        return matched

    def as_prompt_block(self, categories: dict[str, list[str]] | None = None) -> str:
        """Render categories as a markdown allow-list block for the LLM prompt."""
        categories = categories or self.categories
        parts: list[str] = []
        for name, kpis in categories.items():
            parts.append("## " + name)
            parts.extend("- " + k for k in kpis)
        return "\n".join(parts)