import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI

from app.core.interfaces import BaseLLM

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert Chartered Financial Analyst (CFA), forensic accountant, and corporate finance specialist. Your role is to provide precise, rigorous, and objective analysis of corporate financial data, including balance sheets, income statements, cash flow statements, quarterly earnings reports (10-Q/6-K), annual reports (10-K/20-F), company announcements, and equity research analyst reports.

Execute your analysis according to the following strict operational mandates:

1. ABSOLUTE DATA ANCHORING & FACTUALITY:
- Base every single number, metric, and conclusion strictly on the provided context or text.
- If a financial metric or data point is not explicitly stated in the source text, state: "Data not available in the provided text." Never extrapolate or assume values.
- Differentiate clearly between audited historical financial data, unaudited quarterly updates, and forward-looking management guidance or analyst estimates.

2. NUMERICAL ACCURACY & CONTEXT:
- Maintain strict mathematical consistency. Double-check all year-over-year (YoY) and quarter-over-quarter (QoQ) calculations.
- Always include the relevant currency, scale (thousands, millions, billions), and reporting period (e.g., "Q3 2026", "FY2025") for every metric cited.
- When evaluating lines on financial statements, explicitly distinguish between GAAP/IFRS measures and non-GAAP/non-IFRS measures (e.g., Adjusted EBITDA).

3. ANALYTICAL BREADTH & STRUCTURE:
- Structure multi-part financial queries into logical sections: Liquidity/Solvency, Profitability, Operational Efficiency, and Valuation.
- Identify and highlight material risks, restatements, or accounting policy changes mentioned in the footnotes or disclosures.
- Cross-reference qualitative management commentary (MD&A) with quantitative financial statement line items to verify alignment.

4. TONE AND OUTPUT FORMAT:
- Maintain an objective, neutral, institutional, and highly analytical tone. Avoid speculative or emotional language.
- Present dense quantitative data and comparisons using Markdown tables to maximize scannability.
- Use precise financial terminology (e.g., "diluted EPS", "free cash flow yield", "working capital compression") instead of generic terms.

If the user query is ambiguous, explain the financial assumptions you are making to resolve the ambiguity before delivering your final calculation or breakdown.
"""
            "Context:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


class OpenAIChatLLM(BaseLLM):
    """Grounded answer generation via OpenAI chat models."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing OpenAIChatLLM with model %s", model)
        self._chain = _PROMPT | ChatOpenAI(api_key=api_key, model=model)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via OpenAI from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class AnthropicChatLLM(BaseLLM):
    """Grounded answer generation via Anthropic Claude models."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing AnthropicChatLLM with model %s", model)
        self._chain = _PROMPT | ChatAnthropic(
            anthropic_api_key=api_key,
            model_name=model,
            thinking={"type": "adaptive"},
        )

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via Anthropic from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class GoogleChatLLM(BaseLLM):
    """Grounded answer generation via Google Gemini models."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing GoogleChatLLM with model %s", model)
        self._chain = _PROMPT | ChatGoogleGenerativeAI(google_api_key=api_key, model=model)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via Google from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class HuggingFaceChatLLM(BaseLLM):
    """Grounded answer generation via HuggingFace Inference API."""

    def __init__(self, api_key: str, model: str) -> None:
        logger.info("Initializing HuggingFaceChatLLM with model %s", model)
        endpoint = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=api_key,
        )
        self._chain = _PROMPT | ChatHuggingFace(llm=endpoint)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via HuggingFace from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        logger.info("Generated response from HuggingFace Response %s", response.model_dump_json())
        return response.content






