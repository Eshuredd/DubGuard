import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { changedTokens, TextComparison } from "./TextComparison";
afterEach(cleanup);
it("highlights whole words and separate meaningful changes without rewriting source text", () => {
  const reference = "Switch the power off, then wait 15 minutes.";
  const text = "Switch the power on, then wait 50 minutes.";
  const tokens = changedTokens(reference, text);
  expect(tokens.filter((t) => t.changed).map((t) => t.text)).toEqual([
    "on",
    "50",
  ]);
  expect(tokens.map((t) => t.text).join("")).toBe(text);
  expect(
    changedTokens(text, reference)
      .filter((t) => t.changed)
      .map((t) => t.text),
  ).toEqual(["off", "15"]);
});
it("makes omissions visible on the approved side and never calls ASR differences violations", () => {
  const { container } = render(
    <TextComparison approved="Do not restart." recognized="Do restart." />,
  );
  expect(container.querySelector("mark")?.textContent).toBe("not");
  expect(
    screen.getByText("Recognized narration · provisional"),
  ).toBeInTheDocument();
  expect(screen.getByText(/not confirmed spoken errors/)).toBeInTheDocument();
});
it("preserves empty, identical, Unicode and long transcripts", () => {
  for (const [a, b] of [
    ["", ""],
    ["power off", "power off"],
    ["बंद करें।", "चालू करें।"],
    ["a ".repeat(1500), "a ".repeat(1500) + "stop"],
  ]) {
    expect(
      changedTokens(a, b)
        .map((t) => t.text)
        .join(""),
    ).toBe(b);
  }
  expect(changedTokens("power off", "power off").some((t) => t.changed)).toBe(
    false,
  );
});
