import { expect, it } from "vitest";
import { waveformPeaks } from "./AudioTransport";
it("derives waveform peaks from actual samples across channels", () => {
  expect(
    waveformPeaks(
      [new Float32Array([0, -0.25, 0.5, 0]), new Float32Array([0, 0, 0, -0.8])],
      2,
    ),
  ).toEqual([0.25, expect.closeTo(0.8, 5)]);
});
it("does not fabricate signal for silence or unavailable samples", () => {
  expect(waveformPeaks([new Float32Array(1000)], 100)).toEqual(
    Array(100).fill(0),
  );
  expect(waveformPeaks([])).toEqual([]);
});
