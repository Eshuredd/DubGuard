import { afterEach, beforeEach, it, expect, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";
import { AudioInput, chooseMime, recordingFilename } from "./Audio";
let stopTrack: ReturnType<typeof vi.fn>;
let track: { stop: ReturnType<typeof vi.fn>; onended: null | (() => void) };
class Recorder {
  static isTypeSupported = vi.fn((_mime: string) => true);
  state = "inactive";
  mimeType = "audio/webm;codecs=opus";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(_s: unknown, _o: unknown) {}
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["stub browser chunks"]) });
    this.onstop?.();
  }
}
function Harness() {
  const [file, setFile] = useState<File | null>(null);
  return <AudioInput file={file} onChange={setFile} />;
}
beforeEach(() => {
  stopTrack = vi.fn();
  track = { stop: stopTrack, onended: null };
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }),
    },
  });
  vi.stubGlobal("MediaRecorder", Recorder);
  Recorder.isTypeSupported.mockReturnValue(true);
  vi.stubGlobal(
    "URL",
    Object.assign(URL, {
      createObjectURL: vi.fn(() => "blob:test"),
      revokeObjectURL: vi.fn(),
    }),
  );
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
it("reads the real input level and releases its audio context when capture is cancelled", async () => {
  const close = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal(
    "AudioContext",
    class {
      state = "running";
      resume = vi.fn().mockResolvedValue(undefined);
      close = close;
      createMediaStreamSource() {
        return { connect: vi.fn() };
      }
      createAnalyser() {
        return {
          fftSize: 256,
          getFloatTimeDomainData: (samples: Float32Array) => samples.fill(0.1),
        };
      }
    },
  );
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  await waitFor(() =>
    expect(
      screen.getByRole("meter", { name: "Microphone input level" }),
    ).toHaveAttribute("value", "40"),
  );
  fireEvent.click(screen.getByText("Cancel recording"));
  await waitFor(() => expect(close).toHaveBeenCalledOnce());
  expect(stopTrack).toHaveBeenCalled();
  expect(screen.queryByRole("meter")).not.toBeInTheDocument();
});
it.each([
  ["audio/webm;codecs=opus", "capture.wav", "webm"],
  ["audio/mp4;codecs=mp4a.40.2", "capture.webm", "mp4"],
  ["audio/wav", "source.wav", "wav"],
  ["audio/mpeg", "source.mp3", "mp3"],
  ["", "original.M4A", "m4a"],
])("preserves %s container extension without conversion", (mime, name, ext) => {
  expect(
    recordingFilename(
      new File(["original"], name, { type: mime }),
      "15 versus 50",
    ),
  ).toBe(`dubguard-15-versus-50-original.${ext}`);
});
it("sanitizes unsafe and reserved filenames", () => {
  expect(
    recordingFilename(
      new File(["x"], "../../bad:name.wav", { type: "audio/wav" }),
    ),
  ).toBe("bad-name.wav");
  expect(
    recordingFilename(new File(["x"], "CON.mp4", { type: "audio/mp4" })),
  ).toBe("dubguard-CON.mp4");
});
it("downloads the same original uploaded File used by preview and revokes on discard", () => {
  const original = new File([new Uint8Array([0, 255, 1, 2])], "original.wav", {
    type: "audio/wav",
  });
  render(<Harness />);
  fireEvent.change(screen.getByLabelText("Upload audio"), {
    target: { files: [original] },
  });
  expect(URL.createObjectURL).toHaveBeenCalledWith(original);
  expect(
    screen.getByRole("link", { name: "Download Original Recording" }),
  ).toHaveAttribute("href", "blob:test");
  expect(
    screen.getByRole("link", { name: "Download Original Recording" }),
  ).toHaveAttribute("download", "original.wav");
  fireEvent.click(screen.getByText("Discard recording"));
  expect(
    screen.queryByRole("link", { name: "Download Original Recording" }),
  ).not.toBeInTheDocument();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:test");
});
it("negotiates MP4 when WebM is unsupported and keeps the recorder MIME", async () => {
  Recorder.isTypeSupported.mockImplementation((mime: string) =>
    mime.startsWith("audio/mp4"),
  );
  expect(chooseMime()).toBe("audio/mp4;codecs=mp4a.40.2");
  class MP4 extends Recorder {
    mimeType = "audio/mp4;codecs=mp4a.40.2";
  }
  vi.stubGlobal("MediaRecorder", MP4);
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  fireEvent.click(await screen.findByText("Start recording"));
  fireEvent.click(screen.getByText("Stop recording"));
  expect(
    screen.getByRole("link", { name: "Download Original Recording" }),
  ).toHaveAttribute("download", "narration.mp4");
  const blob = vi.mocked(URL.createObjectURL).mock.calls[0][0] as File;
  expect(blob.type).toBe("audio/mp4;codecs=mp4a.40.2");
  expect(blob.size).toBe(new Blob(["stub browser chunks"]).size);
});
it("does not request microphone permission on load", () => {
  render(<Harness />);
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
});
it("handles permission denial", async () => {
  vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(
    new DOMException("denied", "NotAllowedError"),
  );
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "permission denied",
  );
});
it("handles an unavailable microphone", async () => {
  vi.mocked(navigator.mediaDevices.getUserMedia).mockRejectedValue(
    new DOMException("not found", "NotFoundError"),
  );
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  expect(await screen.findByRole("alert")).toHaveTextContent("No microphone");
});
it("detects unsupported recording formats before requesting permission", () => {
  Recorder.isTypeSupported.mockReturnValue(false);
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "No supported recording format",
  );
  expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
});
it("records, stops tracks, previews and discards without submitting", async () => {
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  fireEvent.click(await screen.findByText("Start recording"));
  expect(screen.getByRole("status")).toHaveTextContent("Recording");
  fireEvent.click(screen.getByText("Stop recording"));
  expect(await screen.findByLabelText("Recording preview")).toBeInTheDocument();
  expect(stopTrack).toHaveBeenCalled();
  fireEvent.click(screen.getByText("Discard recording"));
  expect(screen.queryByLabelText("Recording preview")).not.toBeInTheDocument();
  expect(URL.revokeObjectURL).toHaveBeenCalled();
});
it("cancels capture and stops all tracks", async () => {
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  fireEvent.click(await screen.findByText("Start recording"));
  fireEvent.click(screen.getByText("Cancel recording"));
  expect(stopTrack).toHaveBeenCalled();
  expect(screen.queryByLabelText("Recording preview")).not.toBeInTheDocument();
});
it("stops a pending permission stream after navigation", async () => {
  let resolve!: (value: MediaStream) => void;
  vi.mocked(navigator.mediaDevices.getUserMedia).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const { unmount } = render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  unmount();
  await act(async () =>
    resolve({ getTracks: () => [track] } as unknown as MediaStream),
  );
  expect(stopTrack).toHaveBeenCalled();
});
it("handles disconnection by discarding interrupted capture", async () => {
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  await screen.findByText("Start recording");
  act(() => track.onended?.());
  expect(screen.getByRole("alert")).toHaveTextContent("disconnected");
  expect(stopTrack).toHaveBeenCalled();
});
it("rejects oversized uploads and unsupported file names", () => {
  render(<Harness />);
  const large = new File(["x"], "large.wav", { type: "audio/wav" });
  Object.defineProperty(large, "size", { value: 10_000_001 });
  fireEvent.change(screen.getByLabelText("Upload audio"), {
    target: { files: [large] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("10 MB");
  fireEvent.change(screen.getByLabelText("Upload audio"), {
    target: { files: [new File(["x"], "audio.txt")] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Unsupported file format",
  );
});
it("rejects an oversized recorded chunk", async () => {
  class Large extends Recorder {
    stop() {
      this.state = "inactive";
      this.ondataavailable?.({ data: new Blob([new Uint8Array(10_000_001)]) });
      this.onstop?.();
    }
  }
  vi.stubGlobal("MediaRecorder", Large);
  render(<Harness />);
  fireEvent.click(screen.getByText("Record narration"));
  fireEvent.click(await screen.findByText("Start recording"));
  fireEvent.click(screen.getByText("Stop recording"));
  expect(screen.getByRole("alert")).toHaveTextContent("size limit");
  expect(screen.queryByLabelText("Recording preview")).not.toBeInTheDocument();
});
it("enforces duration limit and releases microphone", async () => {
  vi.useFakeTimers();
  render(<Harness />);
  await act(async () => fireEvent.click(screen.getByText("Record narration")));
  fireEvent.click(screen.getByText("Start recording"));
  act(() => vi.advanceTimersByTime(60_200));
  expect(stopTrack).toHaveBeenCalled();
  expect(screen.getByLabelText("Recording preview")).toBeInTheDocument();
  vi.useRealTimers();
});
