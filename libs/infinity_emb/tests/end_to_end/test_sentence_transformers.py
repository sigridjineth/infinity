import pytest
import torch
from asgi_lifespan import LifespanManager
from httpx import AsyncClient
from sentence_transformers import SentenceTransformer  # type: ignore

from infinity_emb import create_server
from infinity_emb.args import EngineArgs
from infinity_emb.transformer.utils import InferenceEngine

PREFIX = "/v1_ct2"
MODEL: str = pytest.DEFAULT_BERT_MODEL  # type: ignore
batch_size = 64 if torch.cuda.is_available() else 8

app = create_server(
    url_prefix=PREFIX,
    engine_args=EngineArgs(
        model_name_or_path=MODEL,
        batch_size=batch_size,
        engine=InferenceEngine.ctranslate2,
    ),
)


@pytest.fixture
def model_base() -> SentenceTransformer:
    return SentenceTransformer(MODEL)


@pytest.fixture()
async def client():
    async with AsyncClient(
        app=app, base_url="http://test", timeout=20
    ) as client, LifespanManager(app):
        yield client


def test_load_model(model_base):
    # this makes sure that the error below is not based on a slow download
    # or internal pytorch errors
    model_base.encode(["This is a test sentence."])


@pytest.mark.anyio
async def test_model_route(client):
    response = await client.get(f"{PREFIX}/models")
    assert response.status_code == 200
    rdata = response.json()
    assert "data" in rdata
    assert rdata["data"].get("id", "") == MODEL
    assert isinstance(rdata["data"].get("stats"), dict)


@pytest.mark.anyio
async def test_embedding(client, model_base, helpers):
    await helpers.embedding_verify(client, model_base, prefix=PREFIX, model_name=MODEL)


@pytest.mark.performance
@pytest.mark.anyio
async def test_batch_embedding(client, get_sts_bechmark_dataset, model_base, helpers):
    await helpers.util_batch_embedding(
        client=client,
        sts_bechmark_dataset=get_sts_bechmark_dataset,
        model_base=model_base,
        prefix=PREFIX,
        model_name=MODEL,
        batch_size=batch_size,
        downsample=2 if torch.cuda.is_available() else 16,
    )
