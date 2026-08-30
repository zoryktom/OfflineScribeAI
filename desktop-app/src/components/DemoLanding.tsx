export const DEMO_LANDING_INTRO =
  "This shows you how an AI drafts a clinical note from a recorded conversation, using a fake patient. It is not accurate enough for real patients yet.";

export const DEMO_COVERAGE_BLURB =
  "In testing, this tool missed 6 of 8 planted errors and gave 3 false alarms out of 4 on caution flags. That's what 'not ready for real patients' looks like in practice.";

type Props = {
  onStart: () => void;
  starting: boolean;
};

export function DemoLanding({ onStart, starting }: Props) {
  return (
    <section className="panel" aria-labelledby="demo-heading">
      <p className="section-label">Synthetic demo</p>
      <h2 id="demo-heading">A fake visit, not a real patient</h2>
      <p className="app-lede">{DEMO_LANDING_INTRO}</p>
      <p className="demo-coverage">{DEMO_COVERAGE_BLURB}</p>
      <p className="caption">
        You can only open preloaded fake conversations. Recording, file upload,
        and chart export are turned off here. This mode does not make the
        underlying draft more accurate.
      </p>
      <div className="row" style={{ marginTop: "1.25rem" }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onStart}
          disabled={starting}
        >
          {starting ? "Loading fake visit…" : "Start the fake visit walkthrough"}
        </button>
      </div>
    </section>
  );
}
