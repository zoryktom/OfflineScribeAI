import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import { NEGATION_DISCLOSURE_STORAGE_KEY } from "../components/NoteReview";

import "@testing-library/jest-dom/vitest";

afterEach(() => {
  cleanup();
  sessionStorage.removeItem(NEGATION_DISCLOSURE_STORAGE_KEY);
});
