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
            """You are an expert Chartered Financial Analyst (CFA), and corporate finance specialist. Your role is to provide precise, rigorous, and objective analysis of corporate financial data, including balance sheets, income statements, cash flow statements, quarterly earnings reports, annual reports, company announcements, and equity research analyst reports.

Use the following context to answer the user's question:
{context}

CRITICAL RULE: Do not repeat, quote, or include the text of the context in your final response. Provide only the direct financial answer. Do not include introductory text like "Based on the context provided".
""",
        ),
        ("human", "{question}"),
    ]
)

# Plain single-turn prompt for the KPI workflow's complete(system, user) seam.
_COMPLETE_PROMPT = ChatPromptTemplate.from_messages(
    [("system", "{system}"), ("human", "{user}")]
)


def _as_text(content) -> str:
    """Coerce LangChain message content (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text" and "text" in block:
                parts.append(block["text"])
        return "".join(parts)
    return str(content)


class OpenAIChatLLM(BaseLLM):
    """Grounded answer generation via OpenAI chat models."""

    def __init__(self, api_key: str, model: str, timeout: float = 3600) -> None:
        logger.info("Initializing OpenAIChatLLM with model %s (timeout=%ss)", model, timeout)
        self._model = ChatOpenAI(api_key=api_key, model=model, timeout=timeout)
        self._chain = _PROMPT | self._model

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via OpenAI from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content

    def complete(self, system: str, user: str) -> str:
        logger.info("Completing via OpenAI (system=%d chars, user=%d chars)", len(system), len(user))
        response = (_COMPLETE_PROMPT | self._model).invoke({"system": system, "user": user})
        return _as_text(response.content)


class AnthropicChatLLM(BaseLLM):
    """Grounded answer generation via Anthropic Claude models."""

    def __init__(self, api_key: str, model: str, timeout: float = 3600) -> None:
        logger.info("Initializing AnthropicChatLLM with model %s (timeout=%ss)", model, timeout)
        self._model = ChatAnthropic(
            anthropic_api_key=api_key,
            model_name=model,
            thinking={"type": "adaptive"},
            timeout=timeout,
        )
        self._chain = _PROMPT | self._model

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via Anthropic from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content

    def complete(self, system: str, user: str) -> str:
        logger.info("Completing via Anthropic (system=%d chars, user=%d chars)", len(system), len(user))
        response = (_COMPLETE_PROMPT | self._model).invoke({"system": system, "user": user})
        return _as_text(response.content)


class GoogleChatLLM(BaseLLM):
    """Grounded answer generation via Google Gemini models."""

    def __init__(self, api_key: str, model: str, timeout: float = 3600) -> None:
        logger.info("Initializing GoogleChatLLM with model %s (timeout=%ss)", model, timeout)
        self._model = ChatGoogleGenerativeAI(
            google_api_key=api_key, model=model, timeout=timeout
        )
        self._chain = _PROMPT | self._model

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via Google from %d context doc(s)", len(context))
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content

    def complete(self, system: str, user: str) -> str:
        logger.info("Completing via Google (system=%d chars, user=%d chars)", len(system), len(user))
        response = (_COMPLETE_PROMPT | self._model).invoke({"system": system, "user": user})
        return _as_text(response.content)


class HuggingFaceChatLLM(BaseLLM):
    """Grounded answer generation via HuggingFace Inference API."""

    def __init__(self, api_key: str, model: str, timeout: float = 3600) -> None:
        logger.info("Initializing HuggingFaceChatLLM with model %s (timeout=%ss)", model, timeout)
        llm = HuggingFaceEndpoint(
            repo_id="deepseek-ai/DeepSeek-R1-0528",
            task="text-generation",
            # DeepSeek-R1 is a reasoning model: it spends a large, variable budget
            # inside <think>...</think> BEFORE emitting the answer. 1024 tokens was
            # exhausted mid-reasoning, so the model never reached the Markdown and
            # the response came back as a truncated, unclosed <think> block. Give it
            # enough headroom to finish thinking AND produce the full report.
            max_new_tokens=8192,
            do_sample=False,
            temperature=0,
            repetition_penalty=1.03,
            huggingfacehub_api_token=api_key,
            provider="auto",  # let Hugging Face choose the best provider for you
            timeout=timeout,
        )

        # Bind the default `text` response_format strategy so the HF router
        # returns full, structured multi-line output instead of collapsing the
        # generation onto a single line.
        self._model = ChatHuggingFace(llm=llm)
        self._chain = _PROMPT | self._model

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        logger.info("Generating answer via HuggingFace from %d context doc(s)", len(context))
        self._model.bind(response_format={"type": "text"})
        response = self._chain.invoke({"question": question, "context": context_text})
        logger.info("Generated response from HuggingFace Response %s", response)
        return _as_text(response.content)

    def complete(self, system: str, user: str) -> str:
        logger.info("Completing via HuggingFace (system=%d chars, user=%d chars)", len(system), len(user))
        # Stream the generation so the HTTP connection keeps receiving tokens.
        # A non-streaming request makes the HF router wait for the full response
        # and return 504 Gateway Time-out on slow/long generations; streaming
        # keeps the connection alive and sidesteps that gateway limit.
        # The KPI workflow now expects a Markdown report, so request `text`
        # (not `json_object`, which would force JSON-only output).
        self._model.bind(response_format={"type": "text"})
        chain = _COMPLETE_PROMPT | self._model
        parts: list[str] = []
        for chunk in chain.stream({"system": system, "user": user}):
            parts.append(_as_text(getattr(chunk, "content", "")))
        return "".join(parts)






