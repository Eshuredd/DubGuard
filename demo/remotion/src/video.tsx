import React from "react";
import {
  AbsoluteFill,
  Sequence,
  Audio,
  OffthreadVideo,
  staticFile,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import cues from "./narration.json";
import subtitles from "./subtitles.json";
import peaks from "./waveform.json";
import amd from "./amd-evidence.json";
import "./style.css";

const C = {
  navy: "#07131e",
  panel: "#102330",
  teal: "#55ddc5",
  white: "#f4f3eb",
  muted: "#9aaeb8",
  amber: "#ffc76d",
  line: "#29414d",
};
const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};
const fade = (f: number, a = 0, b = 18) =>
  interpolate(f, [a, b], [0, 1], clamp);
const ease = (f: number, delay = 0) =>
  spring({
    frame: f - delay,
    fps: 30,
    config: { damping: 22, stiffness: 95, mass: 0.9 },
  });
const stamp = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function Mark({ size = 74 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 80 80">
      <rect
        x="1"
        y="1"
        width="78"
        height="78"
        rx="21"
        fill="#143b3c"
        stroke="#4b827c"
      />
      {[20, 33, 49, 27, 39].map((h, i) => (
        <rect
          key={i}
          x={18 + i * 10}
          y={(80 - h) / 2}
          width="4"
          height={h}
          rx="2"
          fill={C.teal}
        />
      ))}
    </svg>
  );
}
function Label({
  children,
  color = C.teal,
}: {
  children: React.ReactNode;
  color?: string;
}) {
  return (
    <div className="eyebrow" style={{ color }}>
      {children}
    </div>
  );
}
function Ambient() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: C.navy, overflow: "hidden" }}>
      <div
        className="grid"
        style={{ transform: `translateY(${f * 0.012}px)` }}
      />
      <div
        style={{
          position: "absolute",
          height: 700,
          width: 700,
          border: "1px solid #25414a",
          borderRadius: "50%",
          top: -370,
          right: -180,
          transform: `scale(${1 + Math.sin(f / 160) * 0.035})`,
        }}
      />
      <div className="left-rail" />
    </AbsoluteFill>
  );
}
function Header({
  number,
  title,
  tag = "DUBGUARD / EVIDENCE STUDIO",
}: {
  number: string;
  title: string;
  tag?: string;
}) {
  return (
    <div className="header">
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <Mark size={45} />
        <span className="header-name">{title}</span>
      </div>
      <div className="header-tag">{tag}</div>
      <div className="chapter">{number} / 07</div>
    </div>
  );
}
function Entry({
  children,
  delay = 0,
  style = {},
}: {
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}) {
  const f = useCurrentFrame(),
    p = ease(f, delay);
  return (
    <div
      style={{
        opacity: fade(f, delay, delay + 15),
        transform: `translateY(${(1 - p) * 38}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function AnimatedWaveform({
  large = false,
  color = C.teal,
  actual = false,
}: {
  large?: boolean;
  color?: string;
  actual?: boolean;
}) {
  const f = useCurrentFrame();
  return (
    <svg
      width="100%"
      height={large ? 230 : 100}
      viewBox={`0 0 1600 ${large ? 230 : 100}`}
      preserveAspectRatio="none"
    >
      <line
        x1="0"
        y1={large ? 115 : 50}
        x2="1600"
        y2={large ? 115 : 50}
        stroke="#31505b"
        strokeWidth="1"
      />
      {peaks.map((p, i) => {
        const h =
          8 +
          Math.pow(p, 0.55) *
            (large ? 170 : 70) *
            (actual ? 1 : 0.55 + 0.45 * Math.sin(f * 0.07 - i * 0.18) ** 2);
        return (
          <rect
            key={i}
            x={i * 10 + 2}
            y={(large ? 230 : 100) / 2 - h / 2}
            width={4}
            height={h}
            rx={2}
            fill={color}
            opacity={i * 10 < (f * 7) % 1700 ? 1 : 0.28}
          />
        );
      })}
    </svg>
  );
}
export function WordDifference() {
  const f = useCurrentFrame();
  const change = interpolate(f, [252, 272], [0, 1], clamp);
  return (
    <div
      style={{
        fontSize: 112,
        fontWeight: 600,
        letterSpacing: -5,
        display: "flex",
        gap: 38,
        alignItems: "center",
      }}
    >
      Switch the power{" "}
      <span
        style={{
          display: "inline-block",
          height: 143,
          width: 245,
          position: "relative",
          overflow: "hidden",
          borderBottom: `3px solid ${change > 0.5 ? C.amber : C.teal}`,
        }}
      >
        <span
          style={{
            position: "absolute",
            color: C.teal,
            transform: `translateY(${-change * 150}px)`,
            opacity: 1 - change,
          }}
        >
          OFF.
        </span>
        <span
          style={{
            position: "absolute",
            color: C.amber,
            transform: `translateY(${(1 - change) * 150}px)`,
            opacity: change,
          }}
        >
          ON.
        </span>
      </span>
    </div>
  );
}
export function CinematicIntro() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <div className="intro-kicker">
        <Mark size={50} />
        <Label>INDUSTRIAL NARRATION / ONE-WORD RISK</Label>
      </div>
      {f < 310 ? (
        <div
          style={{
            position: "absolute",
            left: 120,
            top: 285,
            right: 120,
            opacity: 1 - fade(f, 285, 309),
          }}
        >
          <Entry>
            <Label color={f < 170 ? C.muted : C.amber}>
              {f < 262 ? "APPROVED NARRATION" : "ILLUSTRATIVE WORD CHANGE"}
            </Label>
            <div style={{ marginTop: 25 }}>
              <WordDifference />
            </div>
          </Entry>
          <div style={{ marginTop: 55 }}>
            <AnimatedWaveform large color={f < 170 ? C.teal : C.amber} />
          </div>
          <div className="micro" style={{ marginTop: 16 }}>
            Illustrative opening · not a model result
          </div>
        </div>
      ) : f < 444 ? (
        <div className="center-stack">
          <Entry>
            <div className="mega">ONE WORD.</div>
            <div className="mega" style={{ fontSize: 94, color: C.amber }}>
              A DIFFERENT
              <br />
              INSTRUCTION.
            </div>
          </Entry>
        </div>
      ) : f < 585 ? (
        <div className="center-stack">
          <Entry>
            <Label>BEFORE CONTENT GOES LIVE</Label>
            <h1 style={{ fontSize: 109, lineHeight: 1.08 }}>
              How do you catch it
              <br />
              <span style={{ color: C.teal }}>before release?</span>
            </h1>
          </Entry>
        </div>
      ) : (
        <ProductReveal />
      )}
      <div className="corner-note">
        AMD DEVELOPER HACKATHON ACT III · INTELLIGENT INDUSTRY
      </div>
    </AbsoluteFill>
  );
}
export function ProductReveal() {
  const f = useCurrentFrame();
  const p = ease(f, 585);
  return (
    <div
      className="center-stack"
      style={{
        opacity: fade(f, 585, 601),
        transform: `translateY(${(1 - p) * 35}px)`,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 32,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Mark size={116} />
        <div style={{ fontSize: 143, fontWeight: 650, letterSpacing: -7 }}>
          DubGuard
        </div>
      </div>
      <p style={{ fontSize: 36, color: C.muted, marginTop: 38 }}>
        Catch the one word that changes everything.
      </p>
    </div>
  );
}

export function AppFootage({
  src,
  offset = 0,
  zoom = 1,
  focus = "50% 50%",
  y = -70,
}: {
  src: string;
  offset?: number;
  zoom?: number;
  focus?: string;
  y?: number;
}) {
  const f = useCurrentFrame();
  const z = zoom + interpolate(f, [0, 600], [0, 0.016], clamp);
  return (
    <div className="footage-shell">
      <div className="footage-toolbar">
        <span className="record-dot" />
        REAL LOCAL BROWSER CAPTURE
        <span style={{ marginLeft: "auto" }}>
          CPU WHISPER · NO LIVE AMD CALL
        </span>
      </div>
      <div
        style={{
          position: "absolute",
          inset: "40px 0 0",
          overflow: "hidden",
          background: "#f1f3f3",
        }}
      >
        <div
          style={{
            width: 1792,
            height: 1008,
            transform: `translateY(${y}px) scale(${z})`,
            transformOrigin: focus,
          }}
        >
          <OffthreadVideo
            src={staticFile(src)}
            startFrom={offset}
            muted
            style={{ width: "100%", height: "100%" }}
          />
        </div>
      </div>
    </div>
  );
}
export function EvidenceHighlight({
  text,
  detail,
  side = "right",
  amber = false,
  top,
}: {
  text: string;
  detail: string;
  side?: "right" | "left";
  amber?: boolean;
  top?: number;
}) {
  const f = useCurrentFrame();
  return (
    <div
      className="callout"
      style={{
        [side]: 100,
        top,
        bottom: top === undefined ? 168 : "auto",
        borderColor: amber ? C.amber : C.teal,
        opacity: fade(f),
        transform: `translateY(${(1 - ease(f)) * 20}px)`,
      }}
    >
      <div
        style={{
          fontSize: 27,
          fontWeight: 650,
          color: amber ? C.amber : C.teal,
        }}
      >
        {text}
      </div>
      <div style={{ fontSize: 19, color: C.white, marginTop: 5 }}>{detail}</div>
    </div>
  );
}
function LandingScene() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <Header number="02" title="Evidence before release" />
      <AppFootage src="landing.mp4" y={-52} />
      <div className="workflow-pills">
        {[
          "Define protected instructions",
          "Record or upload",
          "Inspect evidence",
          "Review before release",
        ].map((t, i) => (
          <div
            key={t}
            style={{
              opacity: fade(f, i * 85, i * 85 + 20),
              borderColor:
                i === Math.min(3, Math.floor(f / 130)) ? C.teal : C.line,
            }}
          >
            <span>{String(i + 1).padStart(2, "0")}</span>
            {t}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
}
function CreateScene() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <Header number="03" title="Your script. Your protected requirements." />
      <AppFootage src="create.mp4" y={-80} />
      {f > 430 && (
        <Sequence from={430}>
          <EvidenceHighlight
            text="Power state must remain OFF"
            detail="Visitor-defined reference · temporary demo policy"
            top={210}
          />
        </Sequence>
      )}
      <div className="scene-note">
        Public Create a Review workflow · no organizational policy approval
      </div>
    </AbsoluteFill>
  );
}
function DemoScene() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <Header
        number="04"
        title={
          f < 440
            ? "A real recording. A real local analysis."
            : "Follow the finding back to its source."
        }
      />
      {f < 240 ? (
        <AppFootage src="upload.mp4" y={-100} />
      ) : (
        <Sequence from={240}>
          <AppFootage
            src="analysis.mp4"
            y={interpolate(f, [650, 730], [-100, -210], clamp)}
            zoom={interpolate(f, [650, 730], [1, 1.12], clamp)}
            focus="100% 50%"
          />
        </Sequence>
      )}
      {f >= 240 && f < 330 && (
        <div className="original-label">
          <span className="record-dot" />
          ORIGINAL HUMAN RECORDING · on-off.wav
        </div>
      )}
      {f > 700 && f < 1010 && (
        <Sequence from={700} durationInFrames={310}>
          <EvidenceHighlight
            text="Suspected polarity reversal"
            detail="Actual outcome: REVIEW REQUIRED"
            amber
            top={210}
          />
        </Sequence>
      )}
      {f > 1050 && (
        <Sequence from={1050}>
          <EvidenceHighlight
            text="0.00–2.00 seconds"
            detail="Approximate ASR span · original audio source"
            top={210}
          />
        </Sequence>
      )}
      <div className="scene-note">
        Prerecorded real analysis · ASR remains provisional · original audio
        preserved
      </div>
    </AbsoluteFill>
  );
}

const stages = [
  ["01", "Original audio", "Preserved source"],
  ["02", "CPU Whisper", "Local transcription"],
  ["03", "Provisional transcript", "Unverified words"],
  ["04", "Protected-rule checks", "Deterministic logic"],
  ["05", "AMD Token Factory", "Optional text review"],
  ["06", "DeepSeek-V4-Flash", "Semantic advice"],
  ["07", "Citation validation", "Exact source spans"],
  ["08", "Human evidence review", "Inspect before deciding"],
];
export function ArchitectureAnimation() {
  const f = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 90, right: 90, top: 220 }}>
      <Label>FROM SOURCE AUDIO TO REVIEWABLE EVIDENCE</Label>
      <h2 style={{ fontSize: 64, margin: "18px 0 46px" }}>
        Local by default.{" "}
        <span style={{ color: C.teal }}>AMD when requested.</span>
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: "45px 32px",
        }}
      >
        {stages.map(([n, title, desc], i) => {
          const p = ease(f, 25 + i * 26);
          return (
            <div
              key={n}
              className="architecture-node"
              style={{
                opacity: fade(f, 25 + i * 26, 40 + i * 26),
                transform: `translateY(${(1 - p) * 24}px)`,
                borderColor: i === 4 || i === 5 ? "#688fa0" : C.line,
              }}
            >
              <span className="node-number">{n}</span>
              <div style={{ fontSize: 28, fontWeight: 600, marginTop: 18 }}>
                {title}
              </div>
              <p style={{ color: C.muted, fontSize: 21 }}>{desc}</p>
              {i !== 3 && i !== 7 && (
                <svg className="node-arrow" width="35" height="25">
                  <path
                    d="M0 12 H26 M19 5 L27 12 L19 19"
                    stroke={C.teal}
                    fill="none"
                    strokeWidth="2"
                    strokeDasharray="45"
                    strokeDashoffset={
                      45 * (1 - fade(f, 40 + i * 26, 60 + i * 26))
                    }
                  />
                </svg>
              )}
            </div>
          );
        })}
      </div>
      <svg
        style={{
          position: "absolute",
          top: 352,
          left: 0,
          overflow: "visible",
          opacity: fade(f, 125, 150),
        }}
        width="1740"
        height="48"
      >
        <path
          d="M1535 0 V22 H205 V44 M198 37 L205 45 L212 37"
          fill="none"
          stroke={C.teal}
          strokeWidth="1.5"
        />
      </svg>
      <div className="boundary-note" style={{ opacity: fade(f, 270, 300) }}>
        <span className="boundary-chip">TEXT ONLY → AMD</span>
        <span>Script + policy + transcript</span>
        <span style={{ marginLeft: "auto", color: C.teal }}>
          Original audio stays local.
        </span>
      </div>
    </div>
  );
}
export function AMDIntegration() {
  const f = useCurrentFrame();
  const spans = amd.citation_checks[0].spans;
  return (
    <AbsoluteFill>
      <Ambient />
      <Header
        number="05"
        title="AMD Token Factory / DeepSeek-V4-Flash"
        tag="OPTIONAL SEMANTIC REVIEW"
      />
      {f < 530 ? (
        <ArchitectureAnimation />
      ) : (
        <div style={{ position: "absolute", top: 190, left: 90, right: 90 }}>
          <Entry>
            <Label color={C.amber}>HISTORICAL LIVE AMD TEXT INFERENCE</Label>
            <h2 style={{ fontSize: 64, margin: "18px 0 12px" }}>
              Advice with inspectable citations.
            </h2>
            <p style={{ fontSize: 26, color: C.muted, margin: "0 0 34px" }}>
              Previously authorized manual-text example · separate from the
              uploaded WAV
            </p>
          </Entry>
          <div className="amd-columns">
            <div className="response-card">
              <Label>VALIDATED RESPONSE EVIDENCE</Label>
              <div className="code-line">
                requirement_id <b>"power-state"</b>
              </div>
              <div className="code-line">
                finding_kind <b>"POLARITY"</b>
              </div>
              {spans.map((s, i) => (
                <div
                  key={s.source}
                  style={{
                    padding: "16px 0",
                    borderTop: `1px solid ${C.line}`,
                    opacity: fade(f, 560 + i * 65, 580 + i * 65),
                  }}
                >
                  <Label color={C.muted}>
                    {s.source.toUpperCase()} · CHARACTERS [{s.start_char},{" "}
                    {s.end_char})
                  </Label>
                  <div
                    style={{
                      fontSize: 34,
                      marginTop: 10,
                      color: i ? C.amber : C.white,
                    }}
                  >
                    {s.quote}
                  </div>
                  <div style={{ fontSize: 19, color: C.teal, marginTop: 8 }}>
                    ✓ Exact source slice · unique · valid mapping
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {[
                [
                  String(amd.citation_checks[0].spans.length),
                  "validated source spans",
                ],
                ["0", "citation issues"],
                [
                  (amd.latency_ms / 1000).toFixed(3) + " s",
                  "observed request latency",
                ],
                [
                  String(amd.usage.total_tokens),
                  "tokens · one historical request",
                ],
              ].map(([big, small], i) => (
                <div
                  key={small}
                  className="metric"
                  style={{ opacity: fade(f, 610 + i * 28, 630 + i * 28) }}
                >
                  <span>{big}</span>
                  <div>{small}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="amd-source">
            Source: reports/phase4/amd_smoke.json + amd_smoke_inspection.json
            <br />
            Returned model: {amd.actual_model} · no additional AMD calls · one
            example, not an accuracy benchmark
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
}

export function HumanReviewScene() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <Header number="06" title="The evidence stays in human hands." />
      <AppFootage src="human.mp4" offset={f > 370 ? 120 : 0} y={-100} />
      {f > 220 && f < 490 && (
        <Sequence from={220} durationInFrames={270}>
          <EvidenceHighlight
            text="Human confirmation pending"
            detail="No listening attestation or approval created"
            amber
          />
        </Sequence>
      )}
      {f > 650 && (
        <Sequence from={650}>
          <EvidenceHighlight
            text="Temporary demo decision"
            detail="Needs further review · evidence exported"
          />
        </Sequence>
      )}
      <div className="scene-note">
        Candidate finding ≠ confirmed speech ≠ authenticated organizational
        sign-off
      </div>
      {f >= 825 && (
        <AbsoluteFill
          style={{
            background: C.navy,
            opacity: fade(f, 825, 840),
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", gap: 45 }}>
            {["Detect.", "Inspect.", "Review."].map((word, i) => (
              <span
                key={word}
                style={{
                  fontSize: 96,
                  fontWeight: 650,
                  color: i === 2 ? C.teal : C.white,
                  opacity: fade(f, 830 + i * 14, 844 + i * 14),
                  transform: `translateY(${(1 - ease(f, 830 + i * 14)) * 30}px)`,
                }}
              >
                {word}
              </span>
            ))}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
}
export function Outro() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <Ambient />
      <Header number="07" title="Small words. Critical differences." />
      {f < 210 ? (
        <div className="center-stack">
          <Label>ILLUSTRATIVE PROTECTED DIFFERENCES</Label>
          <div
            style={{
              display: "flex",
              gap: 75,
              justifyContent: "center",
              marginTop: 70,
            }}
          >
            {[
              ["OFF", "ON"],
              ["15", "50"],
              ["BEFORE", "AFTER"],
            ].map(([a, b], i) => (
              <div
                key={a}
                style={{
                  fontSize: i === 2 ? 59 : 91,
                  fontWeight: 650,
                  opacity: fade(f, i * 32, i * 32 + 20),
                  transform: `translateY(${(1 - ease(f, i * 32)) * 25}px)`,
                }}
              >
                <span>{a}</span>
                <span style={{ color: C.amber, margin: "0 17px" }}>≠</span>
                <span>{b}</span>
              </div>
            ))}
          </div>
          <p style={{ color: C.muted, fontSize: 25, marginTop: 65 }}>
            Examples of what to protect · not additional measured detection
            results
          </p>
        </div>
      ) : f < 630 ? (
        <div style={{ position: "absolute", top: 250, left: 160, right: 160 }}>
          <Label>BUILT AROUND REVIEWABLE EVIDENCE</Label>
          <div style={{ marginTop: 34 }}>
            {[
              "Local speech transcription",
              "Protected instruction verification",
              "AMD-assisted semantic review",
              "Source-linked evidence",
              "Human-controlled decisions",
            ].map((t, i) => (
              <div
                key={t}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 30,
                  fontSize: 48,
                  lineHeight: 1.75,
                  opacity: fade(f, 210 + i * 25, 230 + i * 25),
                  transform: `translateX(${(1 - ease(f, 210 + i * 25)) * 50}px)`,
                }}
              >
                <span
                  style={{
                    fontSize: 23,
                    color: C.teal,
                    fontFamily: "Consolas",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                {t}
              </div>
            ))}
          </div>
          <p style={{ fontSize: 23, color: C.amber, marginTop: 25 }}>
            Review aid · critical or unresolved evidence is never automatic
            approval.
          </p>
        </div>
      ) : (
        <div className="center-stack" style={{ top: 235 }}>
          <div
            style={{
              display: "flex",
              gap: 25,
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <Mark size={112} />
            <span style={{ fontSize: 129, fontWeight: 650, letterSpacing: -6 }}>
              DubGuard
            </span>
          </div>
          <p style={{ fontSize: 39, color: C.teal, margin: "38px 0 55px" }}>
            Catch the one word that changes everything.
          </p>
          <div style={{ fontSize: 25, color: C.white }}>
            github.com/Eshuredd/DubGuard
          </div>
          <div style={{ fontSize: 24, color: C.muted, marginTop: 18 }}>
            134-209-145-248.sslip.io
          </div>
          <div style={{ fontSize: 17, color: C.muted, marginTop: 12 }}>
            Public installation: older UI · current source demonstrated locally
          </div>
          <div className="final-track">
            AMD DEVELOPER HACKATHON ACT III / INTELLIGENT INDUSTRY
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
}

export function Subtitles() {
  const t = useCurrentFrame() / 30;
  const cue = subtitles.find((c) => t >= c.start && t < c.end);
  if (!cue) return null;
  return (
    <div className="subtitles">
      <span>{cue.text}</span>
    </div>
  );
}
function Cuts() {
  const f = useCurrentFrame();
  const boundaries = [750, 1350, 2100, 3450, 4650, 5550];
  const near = boundaries.find((b) => f >= b - 9 && f < b + 12);
  if (!near) return null;
  const p = interpolate(f, [near - 9, near, near + 12], [-110, 0, 110]);
  return (
    <AbsoluteFill
      style={{
        background: "#11383c",
        transform: `translateX(${p}%)`,
        zIndex: 80,
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 6,
          top: 0,
          bottom: 0,
          right: 0,
          background: C.teal,
        }}
      />
    </AbsoluteFill>
  );
}
export function Film() {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        background: C.navy,
        color: C.white,
        fontFamily: "Segoe UI,Arial,sans-serif",
      }}
    >
      <Sequence durationInFrames={750}>
        <CinematicIntro />
      </Sequence>
      <Sequence from={750} durationInFrames={600}>
        <LandingScene />
      </Sequence>
      <Sequence from={1350} durationInFrames={750}>
        <CreateScene />
      </Sequence>
      <Sequence from={2100} durationInFrames={1350}>
        <DemoScene />
      </Sequence>
      <Sequence from={3450} durationInFrames={1200}>
        <AMDIntegration />
      </Sequence>
      <Sequence from={4650} durationInFrames={900}>
        <HumanReviewScene />
      </Sequence>
      <Sequence from={5550} durationInFrames={900}>
        <Outro />
      </Sequence>
      {cues.map((c) => (
        <Sequence
          key={c.id}
          from={Math.round(c.start * 30)}
          durationInFrames={Math.ceil((c.end - c.start + 0.1) * 30)}
        >
          <Audio src={staticFile(`narration/${c.id}.m4a`)} />
        </Sequence>
      ))}
      <Sequence from={2340} durationInFrames={78}>
        <Audio src={staticFile("on-off.wav")} volume={7} />
      </Sequence>
      <Subtitles />
      <div className="film-progress">
        <div style={{ width: `${(f / 6449) * 100}%` }} />
      </div>
      <Cuts />
    </AbsoluteFill>
  );
}
