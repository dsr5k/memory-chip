from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.core.config import get_settings

settings = get_settings()


class VectorSearch:
    def __init__(self):
        self._client = QdrantClient(url=settings.qdrant_url)

    def search(self, query: str, top_k: int = 5):
        try:
            points = self._client.query_points(
                collection_name=settings.qdrant_collection,
                query=[0.0] * 384,
                with_payload=True,
                limit=top_k,
            )
            return [
                {
                    'id': str(point.id),
                    'score': float(point.score),
                    'payload': point.payload or {},
                }
                for point in points.points
            ]
        except Exception:
            return [
                {
                    'id': 'stub',
                    'score': 0.0,
                    'payload': {'note': 'Qdrant not initialized yet', 'query': query},
                }
            ]
