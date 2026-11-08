import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "./App";
import { ROUTES, applyLegacyRedirect, resyncLocation } from "./router";

function goTo(url: string) {
  window.history.replaceState(null, "", url);
  resyncLocation();
}

function renderAt(url: string) {
  goTo(url);
  return render(<App />);
}

const H1: Record<(typeof ROUTES)[number], RegExp> = {
  "/": /every state's early learning standards, as structured data/i,
  "/research": /recovering the structure of early learning standards/i,
  "/data": /what “machine-readable” means/i,
  "/for-states": /your standards, ready for the systems that use them/i,
  "/for-researchers": /compare states' expectations/i,
  "/for-curriculum": /align to every state from one dataset/i,
  "/about": /emily cheyne/i,
  "/brief": /every state's early learning standards, as structured data/i,
  "/contact": /contact us/i,
  "/privacy": /privacy policy/i,
  "/terms": /terms of service/i,
};

beforeEach(() => {
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});

afterEach(() => {
  cleanup();
  goTo("/");
});

describe("routing", () => {
  it.each(ROUTES)("renders %s at its real path", (path) => {
    renderAt(path);
    expect(
      screen.getByRole("heading", { level: 1, name: H1[path] }),
    ).toBeInTheDocument();
  });

  it("renders a not-found page for an unknown path", () => {
    renderAt("/planning");
    expect(
      screen.getByRole("heading", { level: 1, name: /page not found/i }),
    ).toBeInTheDocument();
  });

  it("tolerates a trailing slash", () => {
    renderAt("/research/");
    expect(
      screen.getByRole("heading", { level: 1, name: H1["/research"] }),
    ).toBeInTheDocument();
  });

  it("sets a per-page document title", () => {
    renderAt("/research");
    expect(document.title).toMatch(/^Recovering the structure.* \| EdTech Co\.$/);
  });

  it.each([
    ["#privacy", "/privacy"],
    ["#terms", "/terms"],
    ["#contact", "/contact"],
  ])("redirects the old %s link to %s", (hash, path) => {
    goTo(`/${hash}`);
    applyLegacyRedirect();
    expect(window.location.pathname).toBe(path);
    expect(window.location.hash).toBe("");
    render(<App />);
    expect(
      screen.getByRole("heading", { level: 1, name: H1[path as "/privacy"] }),
    ).toBeInTheDocument();
  });

  it("navigates client-side when an internal link is clicked", () => {
    renderAt("/");
    const pushSpy = vi.spyOn(window.history, "pushState");
    act(() => {
      fireEvent.click(screen.getByRole("link", { name: "For state agencies" }));
    });
    expect(pushSpy).toHaveBeenCalledWith(null, "", "/for-states");
    expect(window.location.pathname).toBe("/for-states");
    expect(
      screen.getByRole("heading", { level: 1, name: H1["/for-states"] }),
    ).toBeInTheDocument();
    pushSpy.mockRestore();
  });

  it("lets modified clicks through to the browser", () => {
    renderAt("/");
    const pushSpy = vi.spyOn(window.history, "pushState");
    const link = screen.getByRole("link", { name: "For state agencies" });
    // Runs after React's root listener: record whether the Link cancelled
    // the click, then cancel it ourselves so jsdom doesn't try to navigate.
    let preventedByLink: boolean | null = null;
    const swallow = (e: Event) => {
      preventedByLink = e.defaultPrevented;
      e.preventDefault();
    };
    window.addEventListener("click", swallow);
    fireEvent.click(link, { metaKey: true });
    window.removeEventListener("click", swallow);
    expect(preventedByLink).toBe(false);
    expect(pushSpy).not.toHaveBeenCalled();
    pushSpy.mockRestore();
  });

  it("follows the browser back button", () => {
    renderAt("/research");
    act(() => {
      window.history.pushState(null, "", "/data");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(
      screen.getByRole("heading", { level: 1, name: H1["/data"] }),
    ).toBeInTheDocument();
  });
});

describe("home page", () => {
  it("shows the evidence strip with the paper's numbers", () => {
    renderAt("/");
    expect(screen.getByText("1.000")).toBeInTheDocument();
    expect(screen.getByText("1 in 297")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /how these were measured/i }),
    ).toHaveAttribute("href", "/research");
  });

  it("shows the Arizona example and links to /data", () => {
    renderAt("/");
    expect(
      screen.getByRole("heading", { level: 2, name: /from a pdf page to structured records/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/US-AZ-2018-LL\.1\.1\.a/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /what the data looks like/i }),
    ).toHaveAttribute("href", "/data");
  });

  it("features only some articles and links to the full list", async () => {
    const { articles } = await import("./data/articles");
    renderAt("/");
    const featured = articles.filter((a) => a.featured);
    expect(featured.length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /read article/i })).toHaveLength(
      featured.length,
    );
    expect(screen.getByRole("link", { name: /all writing/i })).toHaveAttribute(
      "href",
      "/about#writing",
    );
  });

  it("no longer has the projects section", () => {
    const { container } = renderAt("/");
    expect(container.querySelector("#projects")).toBeNull();
  });
});

describe("links", () => {
  it("no rendered link still uses the old hash routes", () => {
    for (const path of ROUTES) {
      const { container, unmount } = renderAt(path);
      const hrefs = Array.from(container.querySelectorAll("a")).map(
        (a) => a.getAttribute("href") ?? "",
      );
      for (const h of hrefs) {
        expect(h, `on ${path}`).not.toMatch(/^#(privacy|terms|contact)$/);
      }
      unmount();
    }
  });

  it("every internal link points at a known route", async () => {
    const { matchRoute } = await import("./router");
    for (const path of ROUTES) {
      const { container, unmount } = renderAt(path);
      for (const a of Array.from(container.querySelectorAll("a"))) {
        const href = a.getAttribute("href") ?? "";
        if (!href.startsWith("/") || href.startsWith("//")) continue;
        const url = new URL(href, "https://edtechco.org");
        if (url.pathname.startsWith("/images/")) continue;
        expect(matchRoute(url.pathname), `${href} on ${path}`).not.toBeNull();
      }
      unmount();
    }
  });
});
