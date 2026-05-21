'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const CHUNK_MS = 5000;
const LIVE_POLL_MS = 3000;

type LiveNote = {
  id: string;
  text: string;
  score: number;
  tags: string | null;
};

export default function HomePage() {
  const [userId, setUserId] = useState('00000000-0000-0000-0000-000000000001');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState('Idle');
  const [chunkCount, setChunkCount] = useState(0);
  const [lastResponse, setLastResponse] = useState<string>('');
  const [liveNotes, setLiveNotes] = useState<LiveNote[]>([]);
  const [liveSummary, setLiveSummary] = useState('');
  const [isLiveRefreshing, setIsLiveRefreshing] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [lastLiveUpdateAt, setLastLiveUpdateAt] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunkIndexRef = useRef(0);
  const liveRefreshInFlightRef = useRef(false);

  const isRecording = useMemo(() => mediaRecorderRef.current?.state === 'recording', [status]);

  const refreshLiveOutputs = useCallback(async (sid: string) => {
    if (liveRefreshInFlightRef.current) {
      return;
    }

    liveRefreshInFlightRef.current = true;
    setIsLiveRefreshing(true);
    setLiveError(null);

    try {
      const [notesResponse, summaryResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/sessions/${sid}/notes`),
        fetch(`${API_BASE_URL}/api/sessions/${sid}/summary`),
      ]);

      const [notesPayload, summaryPayload] = await Promise.all([notesResponse.json(), summaryResponse.json()]);

      if (!notesResponse.ok) {
        throw new Error(`Failed to fetch notes: ${JSON.stringify(notesPayload)}`);
      }

      if (!summaryResponse.ok) {
        throw new Error(`Failed to fetch summary: ${JSON.stringify(summaryPayload)}`);
      }

      setLiveNotes(Array.isArray(notesPayload) ? notesPayload : []);
      setLiveSummary(typeof summaryPayload?.summary === 'string' ? summaryPayload.summary : '');
      setLastLiveUpdateAt(new Date().toLocaleTimeString());
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLiveError(message);
    } finally {
      setIsLiveRefreshing(false);
      liveRefreshInFlightRef.current = false;
    }
  }, []);

  useEffect(() => {
    if (!sessionId) {
      return;
    }

    void refreshLiveOutputs(sessionId);
    const intervalId = window.setInterval(() => {
      void refreshLiveOutputs(sessionId);
    }, LIVE_POLL_MS);

    return () => window.clearInterval(intervalId);
  }, [refreshLiveOutputs, sessionId]);

  async function createSession(): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/sessions/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.status}`);
    }

    const payload = await response.json();
    return payload.id;
  }

  async function startCapture() {
    try {
      setStatus('Requesting microphone permission...');
      setChunkCount(0);
      setLastResponse('');
      setLiveNotes([]);
      setLiveSummary('');
      setLiveError(null);
      setLastLiveUpdateAt(null);
      const sid = await createSession();
      setSessionId(sid);

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunkIndexRef.current = 0;

      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = async (event: BlobEvent) => {
        if (!event.data || event.data.size === 0 || !sid) {
          return;
        }

        const now = new Date();
        const startedAt = new Date(now.getTime() - CHUNK_MS);
        const formData = new FormData();
        formData.append('session_id', sid);
        formData.append('chunk_index', String(chunkIndexRef.current));
        formData.append('started_at', startedAt.toISOString());
        formData.append('ended_at', now.toISOString());
        formData.append('audio', event.data, `chunk-${chunkIndexRef.current}.webm`);

        const ingestResponse = await fetch(`${API_BASE_URL}/api/ingest/chunk`, {
          method: 'POST',
          body: formData,
        });

        const ingestPayload = await ingestResponse.json();
        if (!ingestResponse.ok) {
          setStatus(`Chunk upload error: ${JSON.stringify(ingestPayload)}`);
          return;
        }

        setChunkCount((count) => count + 1);
        setLastResponse(JSON.stringify(ingestPayload, null, 2));
        void refreshLiveOutputs(sid);
        chunkIndexRef.current += 1;
      };

      recorder.start(CHUNK_MS);
      setStatus('Recording and streaming chunks...');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`Error: ${message}`);
    }
  }

  async function stopCapture() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;

    if (sessionId) {
      await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/end`, { method: 'POST' });
    }

    setStatus('Session ended');
  }

  return (
    <main>
      <h1>Memory Chip · Web-First MVP</h1>
      <p>
        Automatic microphone capture with chunk streaming. No manual uploads. Backend API: <code>{API_BASE_URL}</code>
      </p>

      <section className="card">
        <h2>Capture Session</h2>
        <label htmlFor="userId">User UUID</label>
        <input
          id="userId"
          value={userId}
          onChange={(event) => setUserId(event.target.value)}
          style={{ marginLeft: 8, width: '100%', marginTop: 8, marginBottom: 12, padding: 8, borderRadius: 6 }}
        />
        <button className="primary" onClick={startCapture} disabled={isRecording}>
          Start Mic Capture
        </button>
        <button className="warn" onClick={stopCapture} disabled={!isRecording && !sessionId}>
          Stop Session
        </button>
        <p>Status: {status}</p>
        <p>Session ID: {sessionId ?? 'not started'}</p>
        <p>Chunks streamed: {chunkCount}</p>
      </section>

      <section className="card">
        <h2>Last Ingestion Response</h2>
        <pre>{lastResponse || 'No chunks uploaded yet.'}</pre>
      </section>

      <section className="card">
        <h2>Live Notes</h2>
        <p>
          {sessionId
            ? isLiveRefreshing
              ? 'Checking for new notes...'
              : `Polling every ${LIVE_POLL_MS / 1000}s for updates.`
            : 'Start a session to see live notes.'}
        </p>
        {lastLiveUpdateAt && <p>Last refreshed at: {lastLiveUpdateAt}</p>}
        {liveError && <p>Status: Live updates unavailable ({liveError})</p>}
        {liveNotes.length > 0 ? (
          <ul>
            {liveNotes.map((note) => (
              <li key={note.id}>
                {note.text}
                {note.tags ? ` (${note.tags})` : ''}
              </li>
            ))}
          </ul>
        ) : (
          <p>No notes generated yet.</p>
        )}
      </section>

      <section className="card">
        <h2>Live Summary</h2>
        <p>{isLiveRefreshing && sessionId ? 'Refreshing summary...' : 'Summary updates automatically as chunks are processed.'}</p>
        <pre>{liveSummary || 'No summary generated yet.'}</pre>
      </section>
    </main>
  );
}
