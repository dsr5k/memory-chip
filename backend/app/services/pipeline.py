from app.models.entities import AudioChunk, Embedding, Flashcard, Note, Summary, Transcript


def transcribe_chunk_stub(chunk: AudioChunk) -> tuple[str, float]:
    # TODO: Integrate faster-whisper or external Whisper API.
    text = f'[stub transcript] chunk {chunk.chunk_index} from session {chunk.session_id}'
    return text, 0.7


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
