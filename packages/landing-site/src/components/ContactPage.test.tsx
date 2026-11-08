import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ContactPage, { buildMailto } from "./ContactPage";
import { resyncLocation } from "../router";
import { CONTACT_REASONS } from "../data/contactReasons";

function renderAt(url: string) {
  window.history.replaceState(null, "", url);
  resyncLocation();
  return render(<ContactPage />);
}

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
  resyncLocation();
});

describe("contact reason dropdown", () => {
  it("offers every reason", () => {
    renderAt("/contact");
    const select = screen.getByLabelText(/what's this about/i);
    const values = Array.from((select as HTMLSelectElement).options).map(
      (o) => o.value,
    );
    expect(values).toEqual(CONTACT_REASONS.map((r) => r.key));
  });

  it("defaults to a general question", () => {
    renderAt("/contact");
    expect(screen.getByLabelText(/what's this about/i)).toHaveValue("general");
  });

  it.each(CONTACT_REASONS.map((r) => r.key))(
    "preselects ?reason=%s",
    (key) => {
      renderAt(`/contact?reason=${key}`);
      expect(screen.getByLabelText(/what's this about/i)).toHaveValue(key);
    },
  );

  it("ignores an unknown reason", () => {
    renderAt("/contact?reason=nonsense");
    expect(screen.getByLabelText(/what's this about/i)).toHaveValue("general");
  });
});

describe("buildMailto", () => {
  const base = {
    name: "Ada",
    email: "ada@example.org",
    organization: "",
    reason: "validate-state" as const,
    message: "Hello",
  };

  it("puts the reason in the subject and body", () => {
    const url = buildMailto(base);
    const params = new URLSearchParams(url.split("?")[1]);
    expect(params.get("subject")).toBe(
      "[Validate my state's data] Contact from Ada",
    );
    expect(params.get("body")).toBe(
      "Name: Ada\nEmail: ada@example.org\nReason: Validate my state's data\n\nHello",
    );
  });

  it("includes the organization only when given", () => {
    const url = buildMailto({ ...base, organization: "AZ DES" });
    const body = new URLSearchParams(url.split("?")[1]).get("body")!;
    expect(body).toContain("Organization: AZ DES\n");
  });
});
