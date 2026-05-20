from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from app.core.config import Settings
from app.models.entities import AudioChunk
from app.services.pipeline import (
    OpenAIWhisperTranscriptionProvider,
    build_transcription_error_result,
    get_transcription_provider,
)


class _FakeTranscriptions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text='hello from whisper')


class _FakeOpenAIClient:
    def __init__(self):
        self.audio = SimpleNamespace(transcriptions=_FakeTranscriptions())


class TranscriptionPipelineTests(TestCase):
    def test_openai_provider_normalizes_webm_opus_content_type(self):
        client = _FakeOpenAIClient()
        provider = OpenAIWhisperTranscriptionProvider(
            api_key='test-key',
            model='whisper-1',
            client=client,
        )

        result = provider.transcribe(
            filename='chunk-0.webm',
            content=b'webm-bytes',
            content_type='audio/webm;codecs=opus',
        )

        self.assertEqual(result.text, 'hello from whisper')
        self.assertIsNone(result.confidence)
        self.assertEqual(result.provider, 'openai_whisper')
        content_type = client.audio.transcriptions.calls[0]['file'][2]
        self.assertEqual(content_type, 'audio/webm')

    def test_provider_factory_supports_openai_whisper(self):
        settings = Settings(
            whisper_provider='openai_whisper',
            openai_api_key='test-key',
            openai_whisper_model='whisper-1',
        )

        provider = get_transcription_provider(settings)

        self.assertIsInstance(provider, OpenAIWhisperTranscriptionProvider)

    def test_transcription_errors_become_low_confidence_placeholder_text(self):
        chunk = AudioChunk(
            id=uuid4(),
            session_id=uuid4(),
            chunk_index=3,
            storage_url='file:///tmp/chunk-3.webm',
            timestamp_start=datetime.now(timezone.utc),
            timestamp_end=datetime.now(timezone.utc),
        )

        with self.assertLogs('app.services.pipeline', level='WARNING'):
            result = build_transcription_error_result(chunk, RuntimeError('boom'))

        self.assertTrue(result.is_error)
        self.assertEqual(result.confidence, 0.0)
        self.assertIn('chunk 3', result.text)
