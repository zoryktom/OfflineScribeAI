import { useEffect, useRef, useState } from "react";

type Props = {
  busy: boolean;
  onSubmit: (file: File) => Promise<void>;
};

export function RecordOrUpload({ busy, onSubmit }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    return () => {
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser cannot record audio. Upload a .wav file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        const recorded = new File([blob], `visit-${Date.now()}.webm`, {
          type: blob.type,
        });
        setFile(recorded);
        stream.getTracks().forEach((track) => track.stop());
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setError("Microphone permission was denied. You can still upload a file.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  async function handleSubmit() {
    if (!file) {
      setError("Choose a recording or upload a file first.");
      return;
    }
    setError(null);
    await onSubmit(file);
  }

  return (
    <section className="panel" aria-labelledby="record-heading">
      <p className="section-label">New visit</p>
      <h2 id="record-heading">Record or upload</h2>
      <p className="caption">
        One recording at a time. English only. Nothing leaves this computer until
        you later sync a reviewed note.
      </p>

      <div className="stack" style={{ marginTop: "1.25rem" }}>
        <label>
          <span className="section-label">Audio file</span>
          <input
            className="file-input"
            type="file"
            accept="audio/*,.wav,.webm,.mp3,.m4a,.ogg,.flac"
            disabled={busy || recording}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
            }}
          />
        </label>

        <div className="row">
          {recording ? (
            <button
              type="button"
              className="btn btn-danger"
              onClick={stopRecording}
            >
              Stop recording
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={startRecording}
              disabled={busy}
            >
              Record with microphone
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleSubmit()}
            disabled={busy || recording || !file}
          >
            {busy ? "Writing note…" : "Transcribe and draft note"}
          </button>
        </div>

        {file ? (
          <p className="caption">Ready: {file.name}</p>
        ) : (
          <p className="caption">
            You can use audio_samples/english_speech_sample.wav to try transcription.
          </p>
        )}
        {error ? (
          <p className="banner is-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </section>
  );
}
