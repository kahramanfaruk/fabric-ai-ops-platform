"""Prompt templates for the grounded operations assistant.

Templates are defined as named constants rather than f-strings so they
can be unit-tested, versioned, and reviewed independently of call sites.
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are an operations assistant for an industrial asset-management platform.
Answer questions ONLY using the provided context excerpts.
If the context does not contain sufficient information to answer, respond:
"I do not have enough information in the available context to answer that question."
Do not fabricate facts, invent data values, or reason beyond the context.
Keep answers concise (≤ 5 sentences) and technically precise.
"""

RAG_USER_TEMPLATE = """Context excerpts (ranked by relevance):
{context}

---
Question: {question}
"""


def build_rag_messages(context: str, question: str) -> list[dict[str, str]]:
    """Construct the messages list for a grounded RAG completion.

    Parameters
    ----------
    context : str
        Concatenated retrieved document chunks.
    question : str
        User question.

    Returns
    -------
    list[dict[str, str]]
        Messages list compatible with the OpenAI chat completions API.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": RAG_USER_TEMPLATE.format(context=context, question=question),
        },
    ]
