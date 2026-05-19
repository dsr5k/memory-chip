import os
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import get_settings

settings = get_settings()


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
        if self._client:
            try:
                self._client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                )
                return f's3://{settings.s3_bucket_name}/{key}'
            except (BotoCoreError, ClientError):
                pass

        target = Path(settings.local_storage_path) / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        return f'file://{os.path.abspath(target)}'
