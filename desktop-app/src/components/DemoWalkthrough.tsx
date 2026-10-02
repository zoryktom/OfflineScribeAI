import { DEMO_COVERAGE_BLURB } from "./DemoLanding";

const STEPS = [
  {
    title: "The conversation",
    body: "This is a written fake conversation used as the recording. In a real workflow you would check whether the speech model heard medication names and symptoms correctly. Wrong words here get copied into the draft and stay wrong if nobody checks.",
  },
  {
    title: "The AI draft",
    body: "This is the SOAP draft the model wrote from that conversation. Checking every sentence against the transcript is the coordination work the system does not do for you. The model can invent details that were never said.",
  },
  {
    title: "Flags",
    body:
      "Highlighted transcript words and “Needs verification (false alarms remain)” labels are hints, not a complete check. " +
      DEMO_COVERAGE_BLURB,
  },
  {
    title: "Named review",
    body: "Save stays blocked until a reviewer types an id. That keeps the review work visible and named instead of letting a draft look finished on its own. It does not mean the note is correct.",
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
