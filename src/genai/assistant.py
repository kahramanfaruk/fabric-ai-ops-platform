"""Public entry point for the grounded operations assistant.

Wires together:
- Secret retrieval (Key Vault)
- Azure OpenAI client
- AI Search client
- RAG chain
- Evaluation (optional)
- Monitoring

Caller usage::

    from src.genai.assistant import OperationsAssistant
    assistant = OperationsAssistant.from_settings(get_settings())
    result = assistant.answer("What caused the pump failure on 2024-03-15?")
    print(result.answer)
"""

from __future__ import annotations

import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from src.aiops.evaluator import evaluate_response
from src.aiops.monitor import record_evaluation_scores
from src.az.ai_search.search_client import OperationsSearchClient
from src.az.keyvault.secret_client import get_secret
from src.common.config import Settings
from src.genai.rag_chain import OperationsRAGChain, RAGResponse

logger = logging.getLogger(__name__)


class OperationsAssistant:
    """Grounded operations assistant backed by RAG + Azure AI Search.

    Parameters
    ----------
    rag_chain : OperationsRAGChain
        Configured RAG chain instance.
    settings : Settings
        Platform settings (used for evaluation and monitoring).
    evaluate : bool
        If True, each response is automatically evaluated by a judge LLM.
    """

    def __init__(
        self,
        rag_chain: OperationsRAGChain,
        settings: Settings,
        evaluate: bool = True,
    ) -> None:
        self._chain = rag_chain
        self._settings = settings
        self._evaluate = evaluate

    @classmethod
    def from_settings(cls, settings: Settings, evaluate: bool = True) -> OperationsAssistant:
        """Construct a fully-wired assistant from platform settings.

        Uses managed identity (DefaultAzureCredential) for both Azure OpenAI
        and AI Search — no API keys in environment variables.

        Parameters
        ----------
        settings : Settings
            Validated platform settings.
        evaluate : bool
            Enable automatic response evaluation.

        Returns
        -------
        OperationsAssistant
            Ready-to-use assistant instance.
        """
        # Azure OpenAI with Entra token provider (no key rotation needed).
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        oai_client = AzureOpenAI(
            azure_endpoint=settings.openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-02-01",
        )

        # AI Search uses a query key from Key Vault.
        search_api_key = get_secret(settings.keyvault_url, "aisearch-query-key")
        search_client = OperationsSearchClient(
            endpoint=settings.aisearch_endpoint,
            index_name=settings.aisearch_index_name,
            api_key=search_api_key,
        )

        chain = OperationsRAGChain(
            openai_client=oai_client,
            search_client=search_client,
            chat_deployment=settings.openai_deployment,
        )
        return cls(rag_chain=chain, settings=settings, evaluate=evaluate)

    def answer(self, question: str) -> RAGResponse:
        """Answer *question* with grounded context from AI Search.

        Parameters
        ----------
        question : str
            Natural-language question from the operator.

        Returns
        -------
        RAGResponse
            Answer with supporting context and source IDs.
        """
        result = self._chain.invoke(question)

        if self._evaluate and result.context_chunks:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            from openai import AzureOpenAI

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            judge_client = AzureOpenAI(
                azure_endpoint=self._settings.openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-02-01",
            )
            try:
                eval_result = evaluate_response(
                    client=judge_client,
                    deployment=self._settings.openai_deployment,
                    context="\n\n".join(result.context_chunks),
                    question=question,
                    response=result.answer,
                )
                record_evaluation_scores(
                    deployment=self._settings.openai_deployment,
                    groundedness=eval_result.groundedness,
                    relevance=eval_result.relevance,
                    coherence=eval_result.coherence,
                )
                if not eval_result.passed:
                    logger.warning(
                        "Response quality below threshold: groundedness=%d, "
                        "relevance=%d, coherence=%d",
                        eval_result.groundedness,
                        eval_result.relevance,
                        eval_result.coherence,
                    )
            except Exception as exc:  # noqa: BLE001
                # Evaluation failure must never block the answer being returned.
                logger.error("Response evaluation failed (non-fatal): %s", exc)

        return result
