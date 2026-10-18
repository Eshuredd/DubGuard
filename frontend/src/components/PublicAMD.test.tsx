import { useState } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, it, expect } from "vitest";
import { PublicAMD } from "./PublicAMD";
afterEach(cleanup);

function Control({ available = true }: { available?: boolean }) {
  const [mode, setMode] = useState<"local" | "amd">("local");
  const [consent, setConsent] = useState(false);
  return (
    <PublicAMD
      mode={mode}
      consent={consent}
      available={available}
      onMode={setMode}
      onConsent={setConsent}
    />
  );
}

describe("public AMD consent", () => {
  it("explains shared quota exhaustion separately from missing configuration", () => {
    render(
      <PublicAMD
        mode="amd"
        consent={false}
        available={false}
        unavailableReason="quota"
        onMode={() => {}}
        onConsent={() => {}}
      />,
    );
    expect(screen.getByText(/Public AMD quota is exhausted/)).toBeVisible();
  });
  it("requires a fresh unchecked consent after each mode switch and has no code field", async () => {
    const user = userEvent.setup();
    render(<Control />);
    expect(screen.queryByRole("checkbox")).toBeNull();
    await user.selectOptions(screen.getByLabelText("Verification mode"), "amd");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.queryByLabelText(/access code/i)).toBeNull();
    expect(
      screen.getByText(/Original audio is not sent to DeepSeek/),
    ).toBeVisible();
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("checkbox")).toBeChecked();
    await user.selectOptions(
      screen.getByLabelText("Verification mode"),
      "local",
    );
    await user.selectOptions(screen.getByLabelText("Verification mode"), "amd");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });
  it("explains missing provider configuration while retaining local mode", async () => {
    render(<Control available={false} />);
    await userEvent.selectOptions(
      screen.getByLabelText("Verification mode"),
      "amd",
    );
    expect(
      screen.getByText(
        "AMD Semantic Review is temporarily unavailable. Local Verification remains available.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("option", { name: "Local Verification" }),
    ).toBeEnabled();
  });
});
