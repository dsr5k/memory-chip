from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.entities import AudioChunk, Embedding, Flashcard, Note, Summary, Transcript
from app.services.pipeline import (
    build_transcription_error_result,
    generate_flashcard_stub,
    generate_summary_stub,
    relevance_score_stub,
    semantic_filter_stub,
    transcribe_chunk,
)
from app.tasks.celery_app import celery_app

TRANSCRIPTION_ERROR_SCORE = 0.0


@celery_app.task(name='app.tasks.pipeline.process_chunk')
def process_chunk(chunk_id: str):
    db = SessionLocal()
    try:
        chunk = db.get(AudioChunk, chunk_id)
        if not chunk:
            return {'status': 'missing_chunk', 'chunk_id': chunk_id}

        try:
            transcription = transcribe_chunk(chunk)
        except Exception as exc:
            transcription = build_transcription_error_result(chunk, exc)

        filtered_text = semantic_filter_stub(transcription.text)
        score = TRANSCRIPTION_ERROR_SCORE if transcription.is_error else relevance_score_stub(filtered_text)

        transcript = Transcript(
            session_id=chunk.session_id,
            chunk_id=chunk.id,
            text=filtered_text,
            confidence=transcription.confidence,
        )
        note = Note(session_id=chunk.session_id, text=filtered_text, score=score, tags='education')

        db.execute(delete(Summary).where(Summary.session_id == chunk.session_id))
        summary = Summary(session_id=chunk.session_id, body=generate_summary_stub(filtered_text))

        db.execute(delete(Flashcard).where(Flashcard.session_id == chunk.session_id))
        question, answer = generate_flashcard_stub(filtered_text)
        flashcard = Flashcard(session_id=chunk.session_id, question=question, answer=answer, source_ref=str(chunk.id))

        embedding = Embedding(source_type='transcript', source_id=str(transcript.id), vector_ref='qdrant://stub')

        db.add_all([transcript, note, summary, flashcard, embedding])
        db.commit()
        return {'status': 'ok', 'chunk_id': chunk_id}
    finally:
        db.close()
