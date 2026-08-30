import { useMemo, useState } from "react";

import type { GroundedSection, Note, ReviewAction, VerificationNeed } from "../api/client";
import { DRAFT_BANNER } from "../api/client";
import { DemoWatermark } from "./DemoWatermark";

export const NEGATION_CHECK_REASON = "negation_or_question";
export const NEGATION_LLM_REASONS = new Set([
  "negation_or_question",
  "denied_by_patient",
  "only_asked_not_confirmed",
]);
export const NEGATION_CHECK_LABEL =
  "Needs verification (false alarms remain)";
export const NEGATION_DISCLOSURE_TEXT =
  "This check caught 6 of 6 denied-symptom probes in current testing and still flagged 2 of 4 benign caution lines. Treat it as a hint, not a complete signal.";
export const NEGATION_DISCLOSURE_STORAGE_KEY =
  "offline-scribe-negation-disclosure-dismissed";

const SECTIONS = [
  "subjective",
  "objective",
  "assessment",
  "plan",
  "codes",
  "followup",
] as const;

type Section = (typeof SECTIONS)[number];
type SoapSection = "subjective" | "objective" | "assessment" | "plan";

const TITLES: Record<Section, string> = {
  subjective: "Subjective",
  objective: "Objective",
  assessment: "Assessment",
  plan: "Plan",
  codes: "Suggested ICD-10 codes",
  followup: "Follow-up",
};

const HINTS: Record<Section, string> = {
  subjective: "The patient’s story, in clinical language. Edit anything that is wrong.",
  objective: "Exam and measurements. Leave “Not documented” if it was not in the visit.",
  assessment: "Your working impression. Suggestions are not diagnoses until you accept them.",
  plan: "What happens next. Keep this short enough to read between patients.",
  codes: "Accept or reject each suggestion. Color is never the only signal.",
  followup: "Last look. Save stores the reviewed note on this computer.",
};

const GROUNDING_KEY: Record<
  SoapSection,
  keyof Pick<
    Note,
    | "subjective_grounding"
    | "objective_grounding"
    | "assessment_grounding"
    | "plan_grounding"
  >
> = {
  subjective: "subjective_grounding",
  objective: "objective_grounding",
  assessment: "assessment_grounding",
  plan: "plan_grounding",
};

function formatTimestamp(seconds: number): string {
  const clamped = Math.max(0, seconds);
  const minutes = Math.floor(clamped / 60);
  const rest = Math.floor(clamped % 60);
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

function SourceAttribution({ grounding }: { grounding?: GroundedSection }) {
  const sources = grounding?.sources ?? [];
  const directlyStated = grounding?.directly_stated ?? true;
  if (directlyStated && sources.length === 0) {
    return null;
  }
  const unclear = !directlyStated && sources.length === 0;

  return (
    <div className="source-block">
      {directlyStated ? null : (
        <p className="source-flag">
          {unclear ? "Sources unclear" : "Not directly stated"}
        </p>
      )}
      {sources.length > 0 ? (
        <details className="source-details">
          <summary>View source</summary>
          <ul className="source-quotes">
            {sources.map((source, index) => (
              <li key={`${source.start_s}-${index}`} className="source-quote">
                <span className="source-time">
                  {formatTimestamp(source.start_s)}–{formatTimestamp(source.end_s)}
                </span>
                {source.text}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function isNegationCheckFlag(item: VerificationNeed): boolean {
  return NEGATION_LLM_REASONS.has(item.reason);
}

function sectionHasNegationCheck(
  flags: VerificationNeed[] | undefined,
  section: string,
): boolean {
  return (flags ?? []).some(
    (item) => item.section === section && isNegationCheckFlag(item),
  );
}

function visitHasNegationCheck(flags: VerificationNeed[] | undefined): boolean {
  return (flags ?? []).some(isNegationCheckFlag);
}

function negationDisclosureAlreadyDismissed(): boolean {
  try {
    return sessionStorage.getItem(NEGATION_DISCLOSURE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function persistNegationDisclosureDismissed(): void {
  try {
    sessionStorage.setItem(NEGATION_DISCLOSURE_STORAGE_KEY, "1");
  } catch {
    // Private-mode or missing storage must not break review.
  }
}

type Props = {
  note: Note;
  saving: boolean;
  onSave: (note: Note, reviewerId: string, actions: ReviewAction[]) => Promise<void>;
  watermark?: string | null;
};

export function NoteReview({ note, saving, onSave, watermark = null }: Props) {
  const [draft, setDraft] = useState<Note>(note);
  const [step, setStep] = useState(0);
  const [reviewerId, setReviewerId] = useState("");
  const [actions, setActions] = useState<ReviewAction[]>([]);
  const [showNegationDisclosure, setShowNegationDisclosure] = useState(
    () =>
      visitHasNegationCheck(note.verification_needs) &&
      !negationDisclosureAlreadyDismissed(),
  );

  const section = SECTIONS[step];
  const isLast = step === SECTIONS.length - 1;

  const progress = useMemo(
    () => `Section ${step + 1} of ${SECTIONS.length}`,
    [step],
  );

  function recordAction(nextSection: string, action: string) {
    setActions((current) => [...current, { section: nextSection, action }]);
  }

  function updateField(field: SoapSection, value: string) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function setCodeAccepted(code: string, accepted: boolean) {
    setDraft((current) => ({
      ...current,
      suggested_icd10: current.suggested_icd10.map((item) =>
        item.code === code ? { ...item, accepted } : item,
      ),
    }));
    recordAction("codes", accepted ? "accept" : "reject");
  }

  const soapSection = section as SoapSection;
  const isSoap =
    section === "subjective" ||
    section === "objective" ||
    section === "assessment" ||
    section === "plan";
  const canSave = reviewerId.trim().length > 0;

  return (
    <section className="panel" aria-labelledby="note-heading">
      {watermark ? <DemoWatermark /> : null}
      <p className="draft-banner" role="status">
        {DRAFT_BANNER}
      </p>
      {showNegationDisclosure ? (
        <div className="negation-disclosure" role="note">
          <p>{NEGATION_DISCLOSURE_TEXT}</p>
          <button
            type="button"
            className="btn btn-secondary negation-disclosure-dismiss"
            onClick={() => {
              persistNegationDisclosureDismissed();
              setShowNegationDisclosure(false);
            }}
          >
            Dismiss
          </button>
        </div>
      ) : null}
      <p className="section-label">SOAP note</p>
      <h2 id="note-heading" className="note-heading">
        Review this note
      </h2>
      <p className="step-index">{progress}</p>
      <p className="section-label">{TITLES[section]}</p>
      <p className="caption" style={{ marginBottom: "1rem" }}>
        {HINTS[section]}
      </p>

      {isSoap && sectionHasNegationCheck(draft.verification_needs, soapSection) ? (
        <p className="verify-flag is-experimental">{NEGATION_CHECK_LABEL}</p>
      ) : null}

      {isSoap ? (
        <>
          <label>
            <span className="visually-hidden">{TITLES[section]}</span>
            <textarea
              className="textarea"
              value={draft[soapSection]}
              onChange={(event) => updateField(soapSection, event.target.value)}
            />
          </label>
          <SourceAttribution grounding={draft[GROUNDING_KEY[soapSection]]} />
        </>
      ) : null}

      {section === "codes" ? (
        <ul className="icd-list">
          {draft.suggested_icd10.map((item) => (
            <li key={item.code} className="icd-item">
              {item.code === "UNMATCHED" ? (
                <>
                  <strong>Manual coding needed</strong>
                  <p className="caption">{item.description}</p>
                </>
              ) : (
                <>
                  {item.accepted !== true ? (
                    <p className="unverified-label">AI-suggested, unverified</p>
                  ) : null}
                  <strong>
                    {item.code}
                    {item.accepted === true ? " · accepted" : null}
                    {item.accepted === false ? " · not used" : null}
                    {item.accepted == null ? " · unaccepted" : null}
                  </strong>
                  <p className="caption">{item.description}</p>
                  <div className="row" style={{ marginTop: "0.65rem" }}>
                    <button
                      type="button"
                      className="btn btn-primary"
                      aria-pressed={item.accepted === true}
                      onClick={() => setCodeAccepted(item.code, true)}
                    >
                      Accept {item.code}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      aria-pressed={item.accepted === false}
                      onClick={() => setCodeAccepted(item.code, false)}
                    >
                      Don’t use {item.code}
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : null}

      {section === "followup" ? (
        <>
          <ul className="follow-up-list">
            {draft.follow_up.map((item) => (
              <li key={item.text} className="follow-up-item">
                <div>{item.text}</div>
                {item.timeframe ? <p className="caption">{item.timeframe}</p> : null}
              </li>
            ))}
          </ul>
          <label className="reviewer-field">
            <span className="section-label">Reviewing provider id</span>
            <input
              className="text-input"
              value={reviewerId}
              onChange={(event) => setReviewerId(event.target.value)}
              autoComplete="off"
              required
            />
            <p className="caption">
              Required. Sync and FHIR dry-run stay blocked until a named reviewer confirms.
            </p>
          </label>
        </>
      ) : null}

      <div className="row" style={{ marginTop: "1.25rem" }}>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setStep((value) => Math.max(0, value - 1))}
          disabled={step === 0 || saving}
        >
          Back
        </button>
        {isLast ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              const soapEdits: ReviewAction[] = (
                ["subjective", "objective", "assessment", "plan"] as const
              )
                .filter((name) => draft[name] !== note[name])
                .map((name) => ({ section: name, action: "edit" }));
              void onSave(draft, reviewerId.trim(), [
                ...actions,
                ...soapEdits,
                { section: "note", action: "confirm" },
              ]);
            }}
            disabled={saving || !canSave}
          >
            {saving ? "Saving…" : "Save reviewed note"}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setStep((value) => value + 1)}
          >
            Continue
          </button>
        )}
      </div>
    </section>
  );
}
