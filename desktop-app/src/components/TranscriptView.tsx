type Props = {
  transcript: string;
  segments?: TranscriptSegment[];
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

export function TranscriptView({ transcript, segments = [] }: Props) {
  const hasSegments = segments.length > 0;

  return (
    <section className="panel" aria-labelledby="transcript-heading">
      <p className="section-label">Transcript</p>
      <h2 id="transcript-heading">What was said</h2>
      <p className="caption" style={{ marginBottom: "1rem" }}>
        Review this before the SOAP note. Timestamps come from the speech model.
        Speaker labels are not assigned yet.
      </p>
      {hasSegments ? (
        <ol className="segment-list">
          {segments.map((segment, index) => (
            <li key={`${segment.start_s}-${index}`} className="segment-item">
              <span className="segment-time">
                {formatTimestamp(segment.start_s)}–{formatTimestamp(segment.end_s)}
              </span>
              <p className="transcript">{segment.text}</p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="transcript">{transcript}</p>
      )}
    </section>
  );
}
