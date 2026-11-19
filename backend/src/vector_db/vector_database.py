import os
import logging
import httpx
from dotenv import load_dotenv
from pymilvus import MilvusClient, DataType
from tqdm import tqdm
import atexit

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "milvus_lite.db")
MILVUS_URI = os.environ.get("MILVUS_DB_PATH", _DEFAULT_DB_PATH)
COLLECTION_NAME = "services_openai_small_384"
DENSE_DIM = 384  # OpenAI
SERVICES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "Services_description_V2.txt")

OPENAI_EMBEDDING_URL = "https://api.openai.com/v1/embeddings"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
_embedding_client = httpx.Client(
    transport=httpx.HTTPTransport(
        retries=3,
        verify=True,
    ),
    timeout=httpx.Timeout(60.0, connect=15.0),
)

atexit.register(_embedding_client.close)

_client: MilvusClient | None = None


def _embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding inputs must be non-empty strings")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing or empty")

    response = _embedding_client.post(
        OPENAI_EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_EMBEDDING_MODEL,
            "input": texts,
            "dimensions": DENSE_DIM,
            "encoding_format": "float",
        },
        timeout=httpx.Timeout(60.0, connect=15.0),
    )

    if response.is_error:
        # Report the provider's error without exposing the API key.
        try:
            error = response.json().get("error", {})
            message = (
                error.get("message", "Embedding request failed")
                if isinstance(error, dict)
                else str(error)
            )
        except ValueError:
            message = "OpenAI returned a non-JSON error response"

        message = message.replace(api_key, "[REDACTED]")
        raise RuntimeError(
            f"OpenAI embeddings failed: HTTP {response.status_code}: {message}"
        )

    payload = response.json()
    items = sorted(payload.get("data", []), key=lambda item: item["index"])

    if [item["index"] for item in items] != list(range(len(texts))):
        raise RuntimeError("OpenAI returned an unexpected set of embedding indices")

    vectors = [item["embedding"] for item in items]

    if any(len(vector) != DENSE_DIM for vector in vectors):
        raise RuntimeError(
            f"Expected {DENSE_DIM}-dimensional embeddings"
        )

    return vectors

def _get_client() -> MilvusClient:
    global _client
    if _client is None:
        _client = MilvusClient(uri=MILVUS_URI)
    return _client


def _create_collection(client: MilvusClient) -> None:
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("service_name", DataType.VARCHAR, max_length=256)
    schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DENSE_DIM)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="dense",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    client.create_collection(COLLECTION_NAME, schema=schema, index_params=index_params)
    logger.info(f"Created Milvus collection '{COLLECTION_NAME}'")


def parse_services(file_content: str) -> list[tuple[str, str]]:
    services = []
    service_blocks = file_content.strip().split('---')
    for block in service_blocks:
        lines = block.strip().split('\n', 1)
        if len(lines) == 2:
            service_name = lines[0].strip()
            service_description = lines[1].strip().replace("\n", "")
            services.append((service_name, service_description))
    return services


def vector_db_push_batch(force_rebuild: bool = False) -> None:
    client = _get_client()

    if client.has_collection(COLLECTION_NAME):
        if not force_rebuild:
            stats = client.get_collection_stats(COLLECTION_NAME)
            if int(stats["row_count"]) > 0:
                logger.info(f"Collection '{COLLECTION_NAME}' already has {stats['row_count']} entities. Skipping index build.")
                return
        logger.warning(f"Dropping existing collection '{COLLECTION_NAME}' for rebuild.")
        client.drop_collection(COLLECTION_NAME)

    _create_collection(client)

    with open(SERVICES_FILE, encoding="utf-8") as f:
        services = parse_services(f.read())

    BATCH_SIZE = 64
    rows = []
    for i in tqdm(range(0, len(services), BATCH_SIZE), desc="Indexing services"):
        batch = services[i: i + BATCH_SIZE]
        texts = [f"{name} {desc}" for name, desc in batch]
        vecs = _embed(texts)
        rows.extend(
            {"service_name": name, "dense": vec}
            for (name, _), vec in zip(batch, vecs)
        )

    client.insert(COLLECTION_NAME, data=rows)
    client.flush(COLLECTION_NAME)
    logger.info(f"Indexed {len(rows)} services into '{COLLECTION_NAME}'.")


def vector_search(user_query: str, limit: int = 3) -> list[str]:
    client = _get_client()
    vector_db_push_batch()  # no-op if collection already populated; lazy init on Lambda
    q_vec = _embed([user_query])
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=q_vec,
        anns_field="dense",
        search_params={"metric_type": "COSINE", "params": {"ef": 100}},
        limit=limit,
        output_fields=["service_name"],
    )
    service_names = [hit["entity"]["service_name"] for hit in results[0]]
    logger.debug(f"vector_search('{user_query}', limit={limit}) -> {service_names}")
    return service_names
