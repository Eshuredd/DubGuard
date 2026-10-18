import { useEffect, useState, type RefObject } from "react";
import type { Transcript } from "../api";
import { Icon } from "./Icon";

export function waveformPeaks(channels: Float32Array[], bins = 240) {
  const length = channels[0]?.length || 0;
  if (!length) return [];
  return Array.from({ length: bins }, (_, i) => {
    const start = Math.floor((i * length) / bins),
      end = Math.floor(((i + 1) * length) / bins);
    const stride = Math.max(1, Math.floor((end - start) / 100));
    let peak = 0;
    for (const channel of channels)
      for (let j = start; j < end; j += stride)
        peak = Math.max(peak, Math.abs(channel[j] || 0));
    return Math.min(1, peak);
  });
}
const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;

export function AudioTransport({
  blob,
  url,
  audioRef,
  label = "Original recording",
  segments = [],
}: {
  blob: Blob;
  url: string;
  audioRef: RefObject<HTMLAudioElement | null>;
  label?: string;
  segments?: Transcript["segments"];
}) {
  const [playing, setPlaying] = useState(false),
    [time, setTime] = useState(0),
    [duration, setDuration] = useState(0),
    [peaks, setPeaks] = useState<number[]>([]),
    [waveState, setWaveState] = useState("Decoding original audio…"),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    let context: AudioContext | undefined;
    setPeaks([]);
    setWaveState("Decoding original audio…");
    setTime(0);
    setDuration(0);
    setPlaying(false);
    setError("");
    async function decode() {
      if (typeof AudioContext === "undefined" || blob.size > 15_000_000) {
        if (alive)
          setWaveState(
            "Waveform unavailable for this audio. Playback remains available.",
          );
        return;
      }
      try {
        context = new AudioContext();
        const buffer = await context.decodeAudioData(await blob.arrayBuffer());
        if (!alive) return;
        setDuration(buffer.duration);
        setPeaks(
          waveformPeaks(
            Array.from({ length: buffer.numberOfChannels }, (_, i) =>
              buffer.getChannelData(i),
            ),
          ),
        );
        setWaveState("Original audio waveform · actual signal amplitude");
      } catch {
        if (alive)
          setWaveState(
            "Waveform unavailable in this browser. Playback remains available.",
          );
      } finally {
        void context?.close().catch(() => {});
      }
    }
    void decode();
    return () => {
      alive = false;
      if (context && context.state !== "closed")
        void context.close().catch(() => {});
    };
  }, [blob]);
  function seek(seconds: number) {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, Math.min(duration, seconds));
      setTime(audioRef.current.currentTime);
    }
  }
  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    setError("");
    if (!audio.paused) audio.pause();
    else
      try {
        await audio.play();
      } catch {
        setError(
          "Playback could not start. Try the native audio controls below.",
        );
      }
  }
  return (
    <div
      className="audio-transport"
      role="group"
      aria-label={
        label === "Recording preview"
          ? "Preview transport"
          : "Source audio transport"
      }
    >
      <div className="transport-bar">
        <span className="transport-source-label">
          <Icon name="wave" size={18} />
          <span>
            {label === "Recording preview" ? "YOUR TAKE" : "SOURCE AUDIO"}
          </span>
        </span>
        <button
          type="button"
          className="transport-icon"
          aria-label="Back 5 seconds"
          disabled={!duration}
          onClick={() => seek(time - 5)}
        >
          <Icon name="back" />
        </button>
        <button
          type="button"
          className="transport-play"
          aria-label={playing ? "Pause audio" : "Play audio"}
          onClick={toggle}
        >
          <Icon name={playing ? "pause" : "play"} />
        </button>
        <button
          type="button"
          className="transport-icon"
          aria-label="Forward 5 seconds"
          disabled={!duration}
          onClick={() => seek(time + 5)}
        >
          <Icon name="forward" />
        </button>
        <label className="rate-label">
          <span className="sr-only">Playback speed</span>
          <select
            aria-label="Playback speed"
            defaultValue="1"
            onChange={(e) => {
              if (audioRef.current)
                audioRef.current.playbackRate = Number(e.target.value);
            }}
          >
            {[0.5, 0.75, 1, 1.25, 1.5, 2].map((speed) => (
              <option key={speed} value={speed}>
                {speed}×
              </option>
            ))}
          </select>
        </label>
        <span
          className="transport-time"
          role="timer"
          aria-live="off"
          aria-label="Audio time"
        >
          {clock(time)} <span>/ {clock(duration)}</span>
        </span>
      </div>
      <div className="waveform-region">
        <div className="waveform-ruler">
          <span>00:00</span>
          <span>ORIGINAL · UNEDITED</span>
          <span>{clock(duration)}</span>
        </div>
        {peaks.length ? (
          <svg
            className="source-waveform"
            viewBox="0 0 1000 100"
            preserveAspectRatio="none"
            aria-label="Waveform decoded from original audio"
            role="img"
          >
            <line x1="0" y1="50" x2="1000" y2="50" className="wave-baseline" />
            {peaks.map((p, i) => (
              <line
                key={i}
                x1={((i + 0.5) * 1000) / peaks.length}
                x2={((i + 0.5) * 1000) / peaks.length}
                y1={50 - p * 46}
                y2={50 + p * 46}
                className="wave-peak"
              />
            ))}
            <line
              x1={duration ? (time / duration) * 1000 : 0}
              x2={duration ? (time / duration) * 1000 : 0}
              y1="0"
              y2="100"
              className="wave-playhead"
            />
          </svg>
        ) : (
          <div className="waveform-empty">{waveState}</div>
        )}
        <label className="seek-label">
          <span className="sr-only">Playback position</span>
          <input
            type="range"
            aria-label="Playback position"
            min="0"
            max={duration || 1}
            step="0.01"
            value={Math.min(time, duration)}
            disabled={!duration}
            onChange={(e) => seek(Number(e.target.value))}
          />
        </label>
        {!!segments.length && (
          <div className="segment-lane" aria-label="Recognized audio spans">
            {segments
              .filter((s) => s.start_seconds != null)
              .map((s) => (
                <button
                  key={s.id}
                  className={
                    time >= (s.start_seconds || 0) &&
                    time < (s.end_seconds || 0)
                      ? "audio-span selected"
                      : "audio-span"
                  }
                  type="button"
                  onClick={() => {
                    seek(s.start_seconds || 0);
                    void audioRef.current?.play().catch(() => {});
                  }}
                  title={s.text}
                >
                  {(s.start_seconds || 0).toFixed(2)} s <span>{s.text}</span>
                </button>
              ))}
          </div>
        )}
      </div>
      <details className="native-playback">
        <summary>Native audio controls & waveform details</summary>
        <audio
          ref={audioRef}
          controls
          src={url}
          preload="metadata"
          aria-label={label}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => {
            if (Number.isFinite(e.currentTarget.duration))
              setDuration(e.currentTarget.duration);
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onError={() =>
            setError(
              "This audio cannot be played in the current browser. Try another supported browser or the original file.",
            )
          }
        />
        <small>
          {waveState}. Waveform preview never changes the original bytes.
          Segment timestamps are approximate.
        </small>
      </details>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
