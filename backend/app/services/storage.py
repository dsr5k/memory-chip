import os
import logging
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def _sanitize_object_key(key: str) -> str:
    normalized = key.replace('\\', '/')
    parts = [segment for segment in normalized.split('/') if segment not in ('', '.')]
    if not parts or any(segment == '..' for segment in parts):
        raise ValueError('Invalid object key')
    return '/'.join(parts)


class AudioStorage:
    def __init__(self):
        self._client = None
        if settings.s3_endpoint_url:
            self._client = boto3.client(
                's3',
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                region_name=settings.s3_region,
                config=Config(signature_version='s3v4'),
            )

    def save(self, key: str, body: bytes, content_type: str) -> str:
        safe_key = _sanitize_object_key(key)

        if self._client:
            try:
                self._client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=safe_key,
                    Body=body,
                    ContentType=content_type,
                )
                return f's3://{settings.s3_bucket_name}/{safe_key}'
            except (BotoCoreError, ClientError):
                logger.exception('Failed to write chunk to S3-compatible storage, falling back to local storage')

        storage_root = Path(settings.local_storage_path).resolve()
        target_name = f'{uuid4().hex}.webm'
        target = storage_root / target_name

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return f'file://{os.path.abspath(target)}'
