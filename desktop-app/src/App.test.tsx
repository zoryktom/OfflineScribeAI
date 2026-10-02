import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App, { CONFIG_CHECK_LABEL } from "./App";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

function jsonResponse(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function assertRestrictedControlsAbsent() {
  expect(screen.queryByRole("button", { name: /Record with microphone/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /Transcribe and draft note/i })).toBeNull();
  expect(screen.queryByLabelText(/Audio file/i)).toBeNull();
  expect(screen.queryByRole("button", { name: /Preview FHIR JSON/i })).toBeNull();
  expect(screen.queryByText(/Workflow review workstation/i)).toBeNull();
}

describe("App first-paint restriction", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("does not show upload or FHIR controls before /health resolves", async () => {
    const health = deferred<{
      status: string;
      stub_mode: boolean;
      ollama_model: string;
      demo_mode: boolean;
    }>();
    const visits = deferred<unknown[]>();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : String(input);
        if (url.endsWith("/health")) {
          return health.promise.then((body) => jsonResponse(body));
        }
        if (url.endsWith("/visits")) {
          return visits.promise.then((body) => jsonResponse(body));
        }
        return Promise.reject(new Error(`unexpected fetch ${url}`));
      }),
    );

    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent(CONFIG_CHECK_LABEL);
    assertRestrictedControlsAbsent();

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });
    expect(screen.getByRole("status")).toHaveTextContent(CONFIG_CHECK_LABEL);
    assertRestrictedControlsAbsent();

    await act(async () => {
      health.resolve({
        status: "ok",
        stub_mode: true,
        ollama_model: "llama3:8b",
        demo_mode: true,
      });
      visits.resolve([]);
    });

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /Start the fake visit walkthrough/i }),
      ).toBeVisible();
    });
    assertRestrictedControlsAbsent();
    expect(screen.queryByText(CONFIG_CHECK_LABEL)).toBeNull();
  });
});
