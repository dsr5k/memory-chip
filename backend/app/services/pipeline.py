import logging
from dataclasses import dataclass
from os.path import basename
from typing import Protocol
from urllib.parse import urlparse

from openai import OpenAI

from app.core.config import Settings, get_settings
from app.models.entities import AudioChunk
from app.services.storage import AudioStorage

logger = logging.getLogger(__name__)
storage = AudioStorage()


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    confidence: float | None
    provider: str
    is_error: bool = False


class TranscriptionProvider(Protocol):
    provider_name: str

    def transcribe(self, *, filename: str, content: bytes, content_type: str) -> TranscriptionResult: ...


def _normalize_audio_content_type(content_type: str) -> str:
    if not content_type:
        return 'audio/webm'
    normalized = content_type.split(';', maxsplit=1)[0].strip().lower()
    if not normalized:
        return 'audio/webm'
    return normalized


def _guess_audio_filename(chunk: AudioChunk) -> str:
    parsed = urlparse(chunk.storage_url)
    candidate = basename(parsed.path.rstrip('/'))
    if candidate:
        return candidate
    return f'chunk-{chunk.chunk_index}.webm'


def _guess_audio_content_type(chunk: AudioChunk) -> str:
    filename = _guess_audio_filename(chunk).lower()
    if filename.endswith('.wav'):
        return 'audio/wav'
    if filename.endswith('.mp3'):
        return 'audio/mpeg'
    if filename.endswith('.m4a'):
        return 'audio/mp4'
    if filename.endswith('.ogg') or filename.endswith('.opus'):
        return 'audio/ogg'
    return 'audio/webm;codecs=opus'


class OpenAIWhisperTranscriptionProvider:
    provider_name = 'openai_whisper'

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        client: OpenAI | None = None,
    ):
        self._model = model
        self._client = client or OpenAI(api_key=api_key, base_url=base_url)

    def transcribe(self, *, filename: str, content: bytes, content_type: str) -> TranscriptionResult:
        response = self._client.audio.transcriptions.create(
            model=self._model,
            file=(filename, content, _normalize_audio_content_type(content_type)),
        )
        text = getattr(response, 'text', '') or ''
        return TranscriptionResult(
            text=text.strip(),
            confidence=None,
            provider=self.provider_name,
        )


class DeepgramTranscriptionProvider:
    provider_name = 'deepgram'

    def transcribe(self, *, filename: str, content: bytes, content_type: str) -> TranscriptionResult:
        raise NotImplementedError('TODO: Implement Deepgram transcription provider')


def _build_transcription_provider(settings: Settings) -> TranscriptionProvider:
    provider = settings.whisper_provider.strip().lower()
    if provider == 'openai_whisper':
        if not settings.openai_api_key:
            raise ValueError('OPENAI_API_KEY is required when WHISPER_PROVIDER=openai_whisper')
        return OpenAIWhisperTranscriptionProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_whisper_model,
            base_url=settings.openai_base_url,
        )
    if provider == 'deepgram':
        return DeepgramTranscriptionProvider()
    raise ValueError(f'Unsupported whisper provider: {settings.whisper_provider}')


def get_transcription_provider(settings: Settings | None = None) -> TranscriptionProvider:
    return _build_transcription_provider(settings or get_settings())


def _sanitize_transcription_error(error: Exception) -> str:
    if isinstance(error, NotImplementedError):
        return 'provider not implemented yet'
    if isinstance(error, ValueError):
        return 'provider is not configured correctly'
    return 'transcription request failed'


def build_transcription_error_result(chunk: AudioChunk, error: Exception) -> TranscriptionResult:
    provider = get_settings().whisper_provider
    logger.warning('Transcription failed for chunk %s using provider %s: %s', chunk.id, provider, error)
    return TranscriptionResult(
        text=(
            f'[transcription unavailable via {provider} '
            f'for chunk {chunk.chunk_index}: {_sanitize_transcription_error(error)}]'
        ),
        confidence=0.0,
        provider=provider,
        is_error=True,
    )


def transcribe_chunk(chunk: AudioChunk) -> TranscriptionResult:
    audio_bytes = storage.load(chunk.storage_url)
    provider = get_transcription_provider()
    return provider.transcribe(
        filename=_guess_audio_filename(chunk),
        content=audio_bytes,
        content_type=_guess_audio_content_type(chunk),
    )


def semantic_filter_stub(text: str) -> str:
    # TODO: Replace with semantic educational filtering model/service.
    return text


def relevance_score_stub(text: str) -> float:
    # TODO: Replace with relevance scoring model/service.
    return 0.5 if text else 0.0


def generate_summary_stub(filtered_text: str) -> str:
    # TODO: Replace with LLM summary generation.
    return f'Summary:\n{filtered_text[:500]}'


def generate_flashcard_stub(filtered_text: str) -> tuple[str, str]:
    # TODO: Replace with LLM flashcard generation.
    return ('What was discussed?', filtered_text[:200] or 'No content')
