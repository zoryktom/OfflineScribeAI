export const DEMO_WATERMARK =
  "SYNTHETIC DEMO — NOT A REAL PATIENT — NOT FOR CLINICAL USE";

export function DemoWatermark() {
  return (
    <p className="demo-watermark" data-testid="demo-watermark">
      {DEMO_WATERMARK}
    </p>
  );
}
