"""Deliberate structured AI action + embedding transports, independent of resumes.

OpenAI-compatible endpoints support local/self-hosted gateways. Nothing is
called without explicit search configuration. No synthetic semantic fallback.
"""

import json
import math

from openai import AsyncOpenAI

from app.ai.prompting import action_prompt
from app.config import settings


class StructuredActions:
    async def run(self, action: str, payload: str, schema: dict):
        if not settings.search_query_model or not settings.search_api_key:
            raise RuntimeError("search_parser_unconfigured")
        async with AsyncOpenAI(
            api_key=settings.search_api_key,
            base_url=settings.search_base_url,
            timeout=15,
            max_retries=0,
        ) as client:
            response = await client.chat.completions.create(
                model=settings.search_query_model,
                messages=[
                    {"role": "system", "content": action_prompt(action)},
                    {"role": "user", "content": payload},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": action,
                        "strict": True,
                        "schema": schema,
                    },
                },
            )
            return json.loads(response.choices[0].message.content)


class EmbeddingProvider:
    @property
    def model(self):
        return settings.search_embedding_model

    @property
    def dimensions(self):
        return settings.search_embedding_dimensions

    async def embed(self, text: str) -> str:
        if not self.model or not settings.search_embedding_api_key:
            raise RuntimeError("embedding_unconfigured")
        async with AsyncOpenAI(
            api_key=settings.search_embedding_api_key,
            base_url=settings.search_embedding_base_url,
            timeout=15,
            max_retries=0,
        ) as client:
            response = await client.embeddings.create(
                model=self.model,
                dimensions=self.dimensions,
                input=text,
            )
        vector = response.data[0].embedding
        if len(vector) != self.dimensions or not all(math.isfinite(v) for v in vector):
            raise ValueError("invalid_embedding_dimensions")
        if not any(vector):
            raise ValueError("zero_embedding")
        return "[" + ",".join(str(float(v)) for v in vector) + "]"


def get_actions():
    return StructuredActions()


def get_embedding_provider():
    return EmbeddingProvider()
