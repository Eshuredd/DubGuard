import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { audioBlob } from "../api";
export const MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4;codecs=mp4a.40.2",
  "audio/mp4",
];
export function chooseMime() {
  return typeof MediaRecorder === "undefined"
    ? ""
    : MIME_TYPES.find((m) => MediaRecorder.isTypeSupported(m)) || "";
}
export function useObjectURL(blob: Blob | null) {
  const [url, setURL] = useState("");
  useEffect(() => {
    if (!blob) {
      setURL("");
      return;
    }
    const value = URL.createObjectURL(blob);
    setURL(value);
    return () => URL.revokeObjectURL(value);
  }, [blob]);
  return url;
}
export function AudioPlayer({
  path,
  credential,
  audioRef,
}: {
  path: string;
  credential?: string;
  audioRef: RefObject<HTMLAudioElement | null>;
}) {
  const [blob, setBlob] = useState<Blob | null>(null),
    [error, setError] = useState("");
  const url = useObjectURL(blob);
  useEffect(() => {
    let alive = true;
    setBlob(null);
    setError("");
    audioBlob(path, credential)
      .then((b) => {
        if (alive) setBlob(b);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [path, credential]);
  return (
    <div className="audio-player">
      {error ? (
        <p role="alert">{error}</p>
      ) : url ? (
        <audio
          ref={audioRef}
          controls
          src={url}
          preload="metadata"
          aria-label="Original recording"
        />
      ) : (
        <p role="status">Loading private original audio…</p>
      )}
      <small>
        Original recording · protected access · segment times are approximate
      </small>
    </div>
  );
}
export function jump(audio: HTMLAudioElement | null, seconds?: number | null) {
  if (audio && seconds != null) {
    audio.currentTime = Math.max(0, seconds - 0.25);
    void audio.play().catch(() => {});
  }
}
export function AudioInput({
  file,
  onChange,
  maxSeconds = 60,
  maxBytes = 10_000_000,
  scenarioName,
}: {
  file: File | null;
  onChange: (f: File | null) => void;
  maxSeconds?: number;
  maxBytes?: number;
  scenarioName?: string;
}) {
  const [phase, setPhase] = useState<
      "idle" | "permission" | "ready" | "recording" | "stopping"
    >("idle"),
    [error, setError] = useState(""),
    [elapsed, setElapsed] = useState(0);
  const stream = useRef<MediaStream | null>(null),
    recorder = useRef<MediaRecorder | null>(null),
    chunks = useRef<Blob[]>([]),
    bytes = useRef(0),
    generation = useRef(0),
    timer = useRef<ReturnType<typeof setInterval> | null>(null),
    begin = useRef(0);
  const url = useObjectURL(file);
  function clearTimer() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }
  function tracks() {
    stream.current?.getTracks().forEach((t) => {
      t.onended = null;
      t.stop();
    });
    stream.current = null;
  }
  function dispose() {
    generation.current++;
    clearTimer();
    if (recorder.current) {
      recorder.current.onstop = null;
      recorder.current.ondataavailable = null;
      recorder.current.onerror = null;
      if (recorder.current.state !== "inactive") recorder.current.stop();
      recorder.current = null;
    }
    tracks();
    chunks.current = [];
  }
  useEffect(() => () => dispose(), []);
  function cancel() {
    dispose();
    onChange(null);
    setElapsed(0);
    setPhase("idle");
  }
  async function prepare() {
    setError("");
    onChange(null);
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "Microphone recording is unavailable. Use HTTPS or localhost and a supported browser, or upload audio.",
      );
      return;
    }
    if (!chooseMime()) {
      setError(
        "No supported recording format. Upload WAV, MP3, WebM/Opus or MP4/AAC.",
      );
      return;
    }
    const id = ++generation.current;
    setPhase("permission");
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (id !== generation.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      media.getTracks().forEach((t) => {
        t.onended = () => {
          cancel();
          setError(
            "Microphone disconnected. The interrupted recording was discarded.",
          );
        };
      });
      setPhase("ready");
    } catch (e) {
      if (id !== generation.current) return;
      setPhase("idle");
      setError(
        (e as DOMException).name === "NotAllowedError"
          ? "Microphone permission denied. Allow access in browser settings or upload audio."
          : "No microphone is available. Check the device connection or upload audio.",
      );
    }
  }
  function stop() {
    clearTimer();
    if (recorder.current?.state === "recording") {
      setPhase("stopping");
      recorder.current.stop();
    }
    tracks();
  }
  function start() {
    if (!stream.current) return;
    try {
      const mime = chooseMime();
      const r = new MediaRecorder(stream.current, { mimeType: mime });
      recorder.current = r;
      chunks.current = [];
      bytes.current = 0;
      const id = generation.current;
      r.ondataavailable = (e) => {
        if (id !== generation.current) return;
        bytes.current += e.data.size;
        if (bytes.current > maxBytes) {
          cancel();
          setError("Recording exceeded the size limit and was discarded.");
          return;
        }
        if (e.data.size) chunks.current.push(e.data);
      };
      r.onerror = () => {
        cancel();
        setError("Recording failed. Please try again or upload an audio file.");
      };
      r.onstop = () => {
        if (id !== generation.current) return;
        tracks();
        clearTimer();
        const actual = r.mimeType || mime;
        const blob = new Blob(chunks.current, { type: actual });
        chunks.current = [];
        if (blob.size) {
          onChange(
            new File(
              [blob],
              `narration.${actual.includes("mp4") ? "mp4" : "webm"}`,
              { type: actual },
            ),
          );
        } else setError("No audio was captured.");
        setPhase("idle");
      };
      r.start(250);
      begin.current = Date.now();
      setElapsed(0);
      setPhase("recording");
      timer.current = setInterval(() => {
        const seconds = (Date.now() - begin.current) / 1000;
        setElapsed(seconds);
        if (seconds >= Math.max(0.1, maxSeconds - 0.5)) stop();
      }, 200);
    } catch {
      cancel();
      setError(
        "This browser could not start the selected recording format. Try upload instead.",
      );
    }
  }
  function select(f?: File) {
    cancel();
    setError("");
    if (!f) return;
    if (!f.size || f.size > maxBytes) {
      setError(`Choose nonempty audio no larger than ${maxBytes / 1e6} MB.`);
      return;
    }
    if (!/\.(wav|mp3|webm|mp4|m4a)$/i.test(f.name)) {
      setError("Unsupported file format. Choose WAV, MP3, WebM or MP4 audio.");
      return;
    }
    onChange(f);
  }
  return (
    <section className="capture" aria-label="Audio input">
      <div className="capture-title">
        <span
          className={phase === "recording" ? "mic live" : "mic"}
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            width="24"
            height="24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <rect x="9" y="2" width="6" height="13" rx="3" />
            <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" />
          </svg>
        </span>
        <div>
          <h3>Your narration</h3>
          <p>
            Record here or upload an existing file. Both use the same
            verification pipeline.
          </p>
        </div>
      </div>
      <div role="status" aria-live="polite">
        {phase === "recording"
          ? `Recording · ${elapsed.toFixed(1)} s / ${maxSeconds} s`
          : phase === "ready"
            ? "Microphone ready. Recording has not started."
            : phase === "permission"
              ? "Waiting for microphone permission…"
              : phase === "stopping"
                ? "Finishing recording…"
                : "Microphone access is requested only when you choose Record narration."}
      </div>
      <div className="actions">
        {phase === "idle" && (
          <button type="button" onClick={prepare}>
            Record narration
          </button>
        )}
        {phase === "ready" && (
          <button type="button" onClick={start}>
            Start recording
          </button>
        )}
        {phase === "recording" && (
          <button type="button" className="danger" onClick={stop}>
            Stop recording
          </button>
        )}
        {phase !== "idle" && (
          <button type="button" className="secondary" onClick={cancel}>
            Cancel recording
          </button>
        )}
        <label className="upload">
          Upload audio
          <input
            aria-label="Upload audio"
            type="file"
            accept=".wav,.mp3,.webm,.mp4,.m4a,audio/*"
            disabled={phase !== "idle"}
            onChange={(e) => {
              select(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      <small>
        Up to {maxSeconds} seconds · {maxBytes / 1e6} MB · WAV / MP3 / WebM /
        MP4 audio
      </small>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {file && (
        <div className="preview">
          <strong>{file.name}</strong>
          <audio
            aria-label="Recording preview"
            controls
            src={url || undefined}
            onLoadedMetadata={(e) => {
              if (
                Number.isFinite(e.currentTarget.duration) &&
                e.currentTarget.duration > maxSeconds + 0.5
              ) {
                cancel();
                setError("Audio exceeds the duration limit.");
              }
            }}
          />
          <div className="actions">
            <a
              className="button secondary"
              href={url || undefined}
              download={recordingFilename(file, scenarioName)}
            >
              Download Original Recording
            </a>
            <button type="button" className="text-button" onClick={cancel}>
              Discard recording
            </button>
          </div>
          <small>
            {file.type || "Original file format"} · Original bytes, no
            conversion. Preview and save locally before analyzing. Quick Test
            server audio expires after 30 minutes; a download is separate from
            retention and transcript annotation.
          </small>
        </div>
      )}
    </section>
  );
}

export function recordingFilename(file: File, scenarioName?: string) {
  const mime = file.type.split(";")[0].toLowerCase();
  const ext =
    (
      {
        "audio/webm": "webm",
        "audio/mp4": "mp4",
        "video/mp4": "mp4",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/x-m4a": "m4a",
      } as Record<string, string>
    )[mime] ||
    file.name.match(/\.(wav|mp3|webm|mp4|m4a)$/i)?.[1].toLowerCase() ||
    "webm";
  const stem =
    (scenarioName
      ? `dubguard-${scenarioName}-original`
      : file.name.replace(/\.[^.]+$/, "")
    )
      .normalize("NFKD")
      .replace(/[^a-zA-Z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 100) || "dubguard-recording";
  return `${/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(stem) ? "dubguard-" : ""}${stem}.${ext}`;
}
