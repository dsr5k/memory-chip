'use client';

import { useMemo, useRef, useState } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const CHUNK_MS = 5000;

export default function HomePage() {
  const [userId, setUserId] = useState('00000000-0000-0000-0000-000000000001');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [status, setStatus] = useState('Idle');
  const [chunkCount, setChunkCount] = useState(0);
  const [lastResponse, setLastResponse] = useState<string>('');

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunkIndexRef = useRef(0);

  const isRecording = useMemo(() => mediaRecorderRef.current?.state === 'recording', [status]);

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
    </main>
  );
}
