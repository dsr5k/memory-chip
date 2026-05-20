from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Memory Chip API'
    database_url: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/memory_chip'
    redis_url: str = 'redis://localhost:6379/0'

    s3_endpoint_url: str | None = 'http://localhost:9000'
    s3_access_key_id: str = 'minioadmin'
    s3_secret_access_key: str = 'minioadmin'
    s3_bucket_name: str = 'memory-chip-audio'
    s3_region: str = 'us-east-1'
    local_storage_path: str = './storage'

    qdrant_url: str = 'http://localhost:6333'
    qdrant_collection: str = 'memory_segments'

    llm_provider: str = 'stub'
    whisper_provider: str = 'stub'

    celery_task_always_eager: bool = False
    process_inline_fallback: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
