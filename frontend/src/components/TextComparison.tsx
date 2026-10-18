import { Fragment, useState, useRef } from "react";
import { Icon } from "./Icon";

// Compare words, not characters: "off" → "on" must highlight the whole word.
// Preserve original punctuation and whitespace; this is a text aid, not inference.
export function changedTokens(reference: string, text: string) {
  const split = (s: string) =>
    s.match(/\s+|[\p{L}\p{N}]+|[^\s\p{L}\p{N}]/gu) || [];
  const a = split(reference),
    b = split(text);
  const matched = new Set<number>();
  if (a.length * b.length <= 250_000) {
    const lengths = Array.from(
      { length: a.length + 1 },
      () => new Uint32Array(b.length + 1),
    );
    for (let i = a.length - 1; i >= 0; i--)
      for (let j = b.length - 1; j >= 0; j--)
        lengths[i][j] =
          a[i] === b[j]
            ? lengths[i + 1][j + 1] + 1
            : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    let i = 0,
      j = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) {
        matched.add(j);
        i++;
        j++;
      } else if (lengths[i + 1][j] >= lengths[i][j + 1]) i++;
      else j++;
    }
  } else {
    // Bound work for long recordings; highlight the changed middle as a phrase.
    let start = 0,
      end = 0;
    while (start < Math.min(a.length, b.length) && a[start] === b[start])
      matched.add(start++);
    while (
      end < Math.min(a.length, b.length) - start &&
      a[a.length - end - 1] === b[b.length - end - 1]
    ) {
      matched.add(b.length - end - 1);
      end++;
    }
  }
  return b.map((text, i) => ({
    text,
    changed: !matched.has(i) && !!text.trim(),
  }));
}

export function Difference({
  approved,
  observed,
}: {
  approved: string;
  observed: string;
}) {
  if (!approved || approved === observed) return <>{observed}</>;
  return (
    <>
      {changedTokens(approved, observed).map((part, i) =>
        part.changed ? (
          <mark key={i}>{part.text}</mark>
        ) : (
          <Fragment key={i}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}

export function TextComparison({
  approved,
  recognized,
  verified = false,
  approvedLines,
  recognizedLines,
  activeIds = [],
  onSeek,
}: {
  approved: string;
  recognized: string;
  verified?: boolean;
  approvedLines?: { id: string; text: string }[];
  recognizedLines?: {
    id: string;
    text: string;
    start_seconds?: number | null;
    uncertain?: boolean | null;
  }[];
  activeIds?: string[];
  onSeek?: (seconds: number) => void;
}) {
  const [query, setQuery] = useState(""),
    [match, setMatch] = useState(0);
  const viewer = useRef<HTMLDivElement>(null);
  const left =
    approvedLines ||
    approved.split("\n").map((text, i) => ({ id: `approved-${i}`, text }));
  const right: {
    id: string;
    text: string;
    start_seconds?: number | null;
    uncertain?: boolean | null;
  }[] =
    recognizedLines ||
    recognized.split("\n").map((text, i) => ({ id: `recognized-${i}`, text }));
  const matches = [...left, ...right].filter(
    (line) =>
      query &&
      line.text.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  ).length;
  const removed = changedTokens(recognized, approved).filter(
    (p) => p.changed && /[\p{L}\p{N}]/u.test(p.text),
  ).length;
  const added = changedTokens(approved, recognized).filter(
    (p) => p.changed && /[\p{L}\p{N}]/u.test(p.text),
  ).length;
  function nextMatch(delta: number) {
    if (!matches) return;
    const next = (match + delta + matches) % matches;
    setMatch(next);
    viewer.current
      ?.querySelectorAll(".search-line")
      [next]?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }
  return (
    <section className="narration-comparison" aria-label="Narration comparison">
      <div className="comparison-toolbar">
        <div>
          <Icon name="script" size={18} />
          <strong>Narration comparison</strong>
          <span className="diff-count">
            {removed} approved-only · {added} recognized-only words
          </span>
        </div>
        <div className="comparison-search">
          <label>
            <span className="sr-only">Search narration lines</span>
            <Icon name="search" size={16} />
            <input
              aria-label="Search narration lines"
              type="search"
              value={query}
              placeholder="Search the text…"
              onChange={(e) => {
                setQuery(e.target.value);
                setMatch(0);
              }}
            />
          </label>
          {query && (
            <>
              <small aria-live="polite">
                {matches
                  ? `${Math.min(match + 1, matches)} / ${matches}`
                  : "No matching lines"}
              </small>
              <button
                className="icon-button"
                aria-label="Previous matching line"
                disabled={!matches}
                onClick={() => nextMatch(-1)}
              >
                ↑
              </button>
              <button
                className="icon-button"
                aria-label="Next matching line"
                disabled={!matches}
                onClick={() => nextMatch(1)}
              >
                ↓
              </button>
            </>
          )}
        </div>
      </div>
      <div className="comparison" ref={viewer}>
        <div>
          <h3>
            <span className="source-dot approved-dot" />
            Approved narration<span className="pane-type">REFERENCE</span>
          </h3>
          <div className="diff-lines">
            {left.map((line, i) => (
              <div
                key={line.id}
                className={
                  "diff-line " +
                  (activeIds.includes(line.id) ? "active-line " : "") +
                  (query &&
                  line.text
                    .toLocaleLowerCase()
                    .includes(query.toLocaleLowerCase())
                    ? "search-line"
                    : "")
                }
              >
                <span className="line-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p>
                  <Difference approved={recognized} observed={line.text} />
                </p>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h3>
            <span className="source-dot recognized-dot" />
            <span>
              {verified
                ? "Human-verified narration"
                : "Recognized narration · provisional"}
            </span>
            <span className="pane-type">
              {verified ? "SAVED HUMAN EVIDENCE" : "ASR · UNVERIFIED"}
            </span>
          </h3>
          <div className="diff-lines">
            {recognized ? (
              right.map((line, i) => (
                <div
                  key={line.id}
                  className={
                    "diff-line " +
                    (activeIds.includes(line.id) ? "active-line " : "") +
                    (query &&
                    line.text
                      .toLocaleLowerCase()
                      .includes(query.toLocaleLowerCase())
                      ? "search-line"
                      : "")
                  }
                >
                  <span className="line-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <p>
                      <Difference approved={approved} observed={line.text} />
                    </p>
                    {line.start_seconds != null && onSeek && (
                      <button
                        className="text-button diff-seek"
                        onClick={() => onSeek(line.start_seconds!)}
                      >
                        <Icon name="play" size={12} />
                        {line.start_seconds.toFixed(2)} s
                      </button>
                    )}
                    {line.uncertain && (
                      <small className="uncertain-label">
                        Uncertain · listen to confirm
                      </small>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p className="diff-empty">
                No spoken text available. Listen to the original recording.
              </p>
            )}
          </div>
        </div>
      </div>
      <p className="comparison-key">
        <mark>Highlighted words</mark> differ between the texts.{" "}
        {verified
          ? "Review the saved human evidence below."
          : "Text differences are not confirmed spoken errors."}
      </p>
    </section>
  );
}
