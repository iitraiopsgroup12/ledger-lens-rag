from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI

from app.core.interfaces import BaseLLM

_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer the user's question using ONLY the "
            "context below. If the context does not contain enough information, say "
            "\"I don't have enough information to answer that question.\"\n\n"
            "Context:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


class OpenAIChatLLM(BaseLLM):
    """Grounded answer generation via OpenAI chat models."""

    def __init__(self, api_key: str, model: str) -> None:
        self._chain = _PROMPT | ChatOpenAI(api_key=api_key, model=model)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class AnthropicChatLLM(BaseLLM):
    """Grounded answer generation via Anthropic Claude models."""

    def __init__(self, api_key: str, model: str) -> None:
        self._chain = _PROMPT | ChatAnthropic(
            anthropic_api_key=api_key,
            model_name=model,
            thinking={"type": "adaptive"},
        )

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class GoogleChatLLM(BaseLLM):
    """Grounded answer generation via Google Gemini models."""

    def __init__(self, api_key: str, model: str) -> None:
        self._chain = _PROMPT | ChatGoogleGenerativeAI(google_api_key=api_key, model=model)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content


class HuggingFaceChatLLM(BaseLLM):
    """Grounded answer generation via HuggingFace Inference API."""

    def __init__(self, api_key: str, model: str) -> None:
        endpoint = HuggingFaceEndpoint(
            repo_id=model,
            huggingfacehub_api_token=api_key,
        )
        self._chain = _PROMPT | ChatHuggingFace(llm=endpoint)

    def generate(self, question: str, context: list[Document]) -> str:
        context_text = "\n\n---\n\n".join(d.page_content for d in context)
        response = self._chain.invoke({"question": question, "context": context_text})
        return response.content






