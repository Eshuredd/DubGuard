import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import { Badge, Findings } from "./Evidence";
import type { Review } from "../api";
afterEach(cleanup);
it("prioritizes unresolved checks without changing their decision indices", () => {
  const onDecision = vi.fn();
  const onAccept = vi.fn();
  const result: Review = {
    engine_version: "test",
    mode: "deterministic",
    safety_notice: "Review aid only.",
    decision: "REVIEW_REQUIRED",
    script_id: "s",
    script_revision: "1",
    policy_id: "p",
    policy_revision: "1",
    findings: [
      {
        rule_id: "FIRST",
        status: "SATISFIED",
        instruction_ids: [],
        approved: [],
        observed: [],
        explanation: "Satisfied first in API order",
      },
      {
        rule_id: "SECOND",
        status: "UNRESOLVED",
        instruction_ids: [],
        approved: [],
        observed: [],
        explanation: "Needs attention",
      },
    ],
  };
  const { container } = render(
    <Findings
      result={result}
      onSeek={() => {}}
      onDecision={onDecision}
      onAccept={onAccept}
    />,
  );
  expect(container.querySelector("article")?.textContent).toContain("SECOND");
  fireEvent.click(screen.getAllByText("Escalate to reviewer")[0]);
  expect(onDecision).toHaveBeenCalledWith(1, "ESCALATED");
  fireEvent.click(screen.getByText("Mark check reviewed"));
  expect(onAccept).toHaveBeenCalledWith(0);
});
it("never labels a pass candidate approved", () => {
  render(<Badge value="PASS_CANDIDATE" />);
  expect(screen.getByText("Pass candidate · not approval")).toBeInTheDocument();
  expect(screen.queryByText(/^approved$/i)).toBeNull();
});
it("only offers acceptance for satisfied checks and seeks actual timestamps", () => {
  const onSeek = vi.fn();
  const onDecision = vi.fn();
  const result: Review = {
    engine_version: "test",
    mode: "deterministic",
    safety_notice: "Review aid only.",
    decision: "CRITICAL_DEVIATION",
    script_id: "s",
    script_revision: "1",
    policy_id: "p",
    policy_revision: "1",
    findings: [
      {
        rule_id: "POLARITY.REVERSED",
        status: "VIOLATION",
        instruction_ids: ["step"],
        constraint_id: "polarity",
        explanation: "Protected state reversed.",
        approved: [],
        observed: [
          {
            source: "observed",
            text: "on",
            start_char: 0,
            end_char: 2,
            start_seconds: 1.2,
            end_seconds: 1.8,
          },
        ],
      },
    ],
  };
  render(
    <Findings
      result={result}
      onSeek={onSeek}
      onAccept={() => {}}
      onDecision={onDecision}
    />,
  );
  expect(screen.queryByText("Mark check reviewed")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText(/1.20–1.80/));
  expect(onSeek).toHaveBeenCalledWith(1.2);
  fireEvent.click(screen.getByText("Request new recording"));
  expect(onDecision).toHaveBeenCalledWith(0, "RERECORD_REQUIRED");
  fireEvent.click(screen.getByText("Escalate to reviewer"));
  expect(onDecision).toHaveBeenCalledWith(0, "ESCALATED");
});
