const STEPS = [
  {
    title: "The conversation",
    body: "This is a written fake conversation used as the recording. In real use you would check whether the speech model heard medication names and symptoms correctly. Wrong words here get copied into the draft.",
  },
  {
    title: "The AI draft",
    body: "This is the SOAP draft the model wrote from that conversation. Check every sentence against the transcript. The model can invent details that were never said.",
  },
  {
    title: "Flags",
    body: "Highlighted transcript words and “Needs verification” labels are hints, not a complete check. In testing, planted errors were often missed and some caution flags were false alarms.",
  },
  {
    title: "Named review",
    body: "Save stays blocked until a reviewer types an id. That is a process gate so a draft cannot be treated as finished without a name. It does not mean the note is correct.",
  },
] as const;

type Props = {
  step: number;
  onNext: () => void;
};

export function DemoWalkthrough({ step, onNext }: Props) {
  const current = STEPS[Math.min(step, STEPS.length - 1)];
  const last = step >= STEPS.length - 1;
  return (
    <section className="panel demo-walkthrough" aria-labelledby="walkthrough-heading">
      <p className="section-label">
        Walkthrough {step + 1} of {STEPS.length}
      </p>
      <h2 id="walkthrough-heading">{current.title}</h2>
      <p>{current.body}</p>
      {last ? null : (
        <div className="row" style={{ marginTop: "1rem" }}>
          <button type="button" className="btn btn-secondary" onClick={onNext}>
            Next explanation
          </button>
        </div>
      )}
    </section>
  );
}
