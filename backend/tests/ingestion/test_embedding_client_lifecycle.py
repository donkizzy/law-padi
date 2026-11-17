import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.chat import runtime
from app.ingestion import embedding
from app.ingestion.stages.embedding_profiles import embedding_provider_for_profile
from app.legal.enums import EmbeddingProviderKind
from app.legal.evidence import default_embedding_provider
from app.legal.models import EmbeddingProfile
from app.main import app


@pytest.mark.parametrize("provider_kind", list(EmbeddingProviderKind))
@pytest.mark.parametrize("for_query", [False, True])
def test_profiles_reuse_one_client_even_on_simultaneous_first_calls(
    provider_kind: EmbeddingProviderKind, for_query: bool
) -> None:
    embedding.close_embedding_providers()
    profile = EmbeddingProfile(
        name="pooled", provider=provider_kind, model_name="test", vector_dimensions=1024
    )
    factory = (
        default_embedding_provider if for_query else embedding_provider_for_profile
    )
    with patch.object(
        embedding.httpx, "Client", wraps=embedding.httpx.Client
    ) as clients:
        with ThreadPoolExecutor(max_workers=4) as executor:
            providers = list(executor.map(lambda _: factory(profile), range(8)))
        assert clients.call_count == 1
        assert all(provider is providers[0] for provider in providers)
        other = profile.model_copy(update={"id": uuid4()})
        assert factory(other) is not providers[0]
        assert clients.call_count == 2
    embedding.close_embedding_providers()
    assert providers[0].client.is_closed
    assert not factory(profile).client.is_closed
    embedding.close_embedding_providers()


@pytest.mark.parametrize("shutdown", ["api", "chat"])
def test_api_and_chat_shutdown_close_shared_embedding_clients(shutdown: str) -> None:
    profile = EmbeddingProfile(
        name="shutdown",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="test",
        vector_dimensions=1024,
    )
    provider = default_embedding_provider(profile)
    if shutdown == "api":
        with TestClient(app):
            assert not provider.client.is_closed
    else:
        asyncio.run(runtime.run_worker("shutdown", stopping=lambda: True))
    assert provider.client.is_closed
