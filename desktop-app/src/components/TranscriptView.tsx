import type { AsrFlag } from "../api/client";
import { DemoWatermark } from "./DemoWatermark";

type Props = {
  transcript: string;
  segments?: TranscriptSegment[];
  asrFlags?: AsrFlag[];
  watermark?: string | null;
};

export type TranscriptSegment = {
  speaker: "provider" | "patient" | "unknown";
  start_s: number;
  end_s: number;
  text: string;
};

function formatTimestamp(seconds: number): string {
  const clamped = Math.max(0, seconds);
  const minutes = Math.floor(clamped / 60);
  const rest = Math.floor(clamped % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

function overlaps(flag: AsrFlag, start: number, end: number): boolean {
  return flag.end_s >= start && flag.start_s <= end;
}

export function TranscriptView({
  transcript,
  segments = [],
  asrFlags = [],
  watermark = null,
}: Props) {
  const hasSegments = segments.length > 0;

  return (
    <section className="panel" aria-labelledby="transcript-heading">
      {watermark ? <DemoWatermark /> : null}
      <p className="section-label">Transcript</p>
      <h2 id="transcript-heading">What was said</h2>
      <p className="caption" style={{ marginBottom: "1rem" }}>
        Review this before the SOAP note. Timestamps come from the speech model.
        Speaker labels are not assigned yet. Highlighted tokens may be
        low-confidence or unusual medication-like words.
      </p>
      {hasSegments ? (
        <ol className="segment-list">
          {segments.map((segment, index) => {
            const flags = asrFlags.filter((flag) =>
              overlaps(flag, segment.start_s, segment.end_s),
            );
            return (
              <li key={`${segment.start_s}-${index}`} className="segment-item">
                <span className="segment-time">
                  {formatTimestamp(segment.start_s)}–{formatTimestamp(segment.end_s)}
                </span>
                <div>
                  <p className={flags.length ? "transcript is-flagged" : "transcript"}>
                    {segment.text}
                  </p>
                  {flags.map((flag, flagIndex) => (
                    <p key={`${flag.start_s}-${flagIndex}`} className="asr-flag">
                      Check “{flag.text}” ({flag.reason.replaceAll("_", " ")})
                    </p>
                  ))}
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="transcript">{transcript}</p>
      )}
    </section>
  );
}
