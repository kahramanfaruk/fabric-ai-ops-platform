"""LLM response evaluator for the grounded operations assistant.

Evaluates three orthogonal quality dimensions:
- Groundedness: fraction of response claims traceable to retrieved context
  (prevents hallucination).
- Relevance: semantic alignment between the user query and the response.
- Coherence: internal logical consistency (no self-contradictions).

Evaluation is performed by a separate judge LLM call to avoid self-serving
bias.  Scores are 0-5 integers following the Azure AI Evaluation rubric.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import APIConnectionError, APIStatusError, AzureOpenAI

from src.common.exceptions import EvaluationError

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM_PROMPT = """You are an objective evaluator of AI assistant responses.
Score each dimension 0 (worst) to 5 (best). Reply ONLY with JSON:
{"groundedness": <int>, "relevance": <int>, "coherence": <int>}
No explanation, no markdown.
"""

_JUDGE_USER_TEMPLATE = """CONTEXT:
{context}

QUESTION:
{question}

RESPONSE:
{response}
"""


@dataclass(frozen=True)
class EvaluationResult:
    """Quality scores for a single assistant response.

    Parameters
    ----------
    groundedness : int
        0-5 score for factual traceability to provided context.
    relevance : int
        0-5 score for query-answer alignment.
    coherence : int
        0-5 score for internal logical consistency.
    """

    groundedness: int
    relevance: int
    coherence: int

    @property
    def passed(self) -> bool:
        """Return True if all dimensions meet the minimum quality bar (≥ 3)."""
        return self.groundedness >= 3 and self.relevance >= 3 and self.coherence >= 3


def evaluate_response(
    client: AzureOpenAI,
    deployment: str,
    context: str,
    question: str,
    response: str,
) -> EvaluationResult:
    """Evaluate a grounded assistant response with a judge LLM.

    Parameters
    ----------
    client : AzureOpenAI
        Authenticated Azure OpenAI client.
    deployment : str
        Judge model deployment name.
    context : str
        Retrieved context chunks concatenated into a single string.
    question : str
        Original user question.
    response : str
        Assistant response to evaluate.

    Returns
    -------
    EvaluationResult
        Quality scores across three dimensions.

    Raises
    ------
    EvaluationError
        If the judge call fails or returns unparseable JSON.
    """
    import json

    user_message = _JUDGE_USER_TEMPLATE.format(
        context=context, question=question, response=response
    )
    try:
        completion = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
            max_tokens=64,
        )
    except (APIStatusError, APIConnectionError) as exc:
        raise EvaluationError(
            f"Judge LLM call failed for deployment '{deployment}': {exc}"
        ) from exc

    raw = completion.choices[0].message.content or ""
    try:
        scores = json.loads(raw)
        return EvaluationResult(
            groundedness=int(scores["groundedness"]),
            relevance=int(scores["relevance"]),
            coherence=int(scores["coherence"]),
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise EvaluationError(
            f"Judge returned non-parseable response: '{raw}'. Expected JSON with keys "
            "groundedness, relevance, coherence."
        ) from exc
