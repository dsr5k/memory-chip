from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.config import get_settings
from app.models.entities import AudioChunk, Flashcard, Note, Session as LearningSession, SessionStatus, Summary, User
from app.schemas.search import SearchRequest
from app.schemas.sessions import SessionCreateRequest, SessionResponse
from app.services.storage import AudioStorage
from app.services.vector import VectorSearch
from app.tasks.pipeline import process_chunk

router = APIRouter(prefix='/api')
storage = AudioStorage()
vector_search = VectorSearch()
settings = get_settings()


@router.post('/sessions/create', response_model=SessionResponse)
def create_session(payload: SessionCreateRequest, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if user is None:
        user = User(
            id=payload.user_id,
            email=f'{payload.user_id}@local.memory-chip',
            password_hash='stub-password-hash',
        )
        db.add(user)
        db.flush()

    session = LearningSession(user_id=payload.user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post('/sessions/{session_id}/end', response_model=SessionResponse)
def end_session(session_id: UUID, db: Session = Depends(get_db)):
    session = db.get(LearningSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    session.status = SessionStatus.ended
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.get('/sessions/{session_id}/status', response_model=SessionResponse)
def session_status(session_id: UUID, db: Session = Depends(get_db)):
    session = db.get(LearningSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    return session


@router.post('/ingest/chunk')
async def ingest_chunk(
    session_id: UUID = Form(...),
    chunk_index: int = Form(...),
    started_at: datetime = Form(...),
    ended_at: datetime = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session = db.get(LearningSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')
    if session.status != SessionStatus.active:
        raise HTTPException(status_code=400, detail='Session is not active')

    payload = await audio.read()
    key = f'{session_id}/{chunk_index}-{int(datetime.now(timezone.utc).timestamp())}.webm'
    try:
        storage_url = storage.save(key=key, body=payload, content_type=audio.content_type or 'audio/webm')
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chunk = AudioChunk(
        session_id=session_id,
        chunk_index=chunk_index,
        storage_url=storage_url,
        timestamp_start=started_at,
        timestamp_end=ended_at,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    try:
        process_chunk.delay(str(chunk.id))
        mode = 'queued'
    except Exception:
        if settings.process_inline_fallback:
            process_chunk(str(chunk.id))
            mode = 'inline'
        else:
            mode = 'failed_to_queue'

    return {'chunk_id': str(chunk.id), 'storage_url': storage_url, 'processing_mode': mode}


@router.get('/sessions/{session_id}/notes')
def get_notes(session_id: UUID, db: Session = Depends(get_db)):
    notes = db.scalars(select(Note).where(Note.session_id == session_id).order_by(Note.created_at.desc())).all()
    return [{'id': str(note.id), 'text': note.text, 'score': note.score, 'tags': note.tags} for note in notes]


@router.get('/sessions/{session_id}/summary')
def get_summary(session_id: UUID, db: Session = Depends(get_db)):
    summary = db.scalar(select(Summary).where(Summary.session_id == session_id).order_by(Summary.created_at.desc()))
    return {'summary': summary.body if summary else ''}


@router.get('/sessions/{session_id}/flashcards')
def get_flashcards(session_id: UUID, db: Session = Depends(get_db)):
    cards = db.scalars(select(Flashcard).where(Flashcard.session_id == session_id).order_by(Flashcard.created_at.desc())).all()
    return [{'id': str(card.id), 'question': card.question, 'answer': card.answer, 'source_ref': card.source_ref} for card in cards]


@router.post('/search')
def search_memory(payload: SearchRequest):
    hits = vector_search.search(query=payload.query, top_k=payload.top_k)
    return {'hits': hits}
