export const DEMO_LANDING_INTRO =
  "This shows the documentation workflow around a fake visit: a model drafts a note, and a person still has to catch what the draft got wrong or left invisible. It is not accurate enough for real patients yet.";

export const DEMO_COVERAGE_BLURB =
  "In testing, the assertion check caught 6 of 6 denied-symptom probes and still gave 2 false alarms out of 4 on caution language (both on safety-net plan language). Drug-name flags still missed 3 of 3 planted garbles. That's what 'not ready for real patients' looks like in practice.";

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
