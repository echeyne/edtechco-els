import { describe, expect, it } from "vitest";
import fc from "fast-check";
import {
  LEGACY_HASH_REDIRECTS,
  ROUTES,
  legacyRedirectTarget,
  matchRoute,
  normalizePath,
} from "./router";

describe("normalizePath", () => {
  it.each([
    ["/", "/"],
    ["", "/"],
    ["/research/", "/research"],
    ["/Research", "/research"],
    ["//data//", "/data"],
    ["data", "/data"],
    ["a /", "/a"],
    [" /about/ ", "/about"],
  ])("%s -> %s", (input, expected) => {
    expect(normalizePath(input)).toBe(expected);
  });

  it("is idempotent", () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        const once = normalizePath(s);
        expect(normalizePath(once)).toBe(once);
      }),
    );
  });

  it("always yields a path starting with a single slash", () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        const p = normalizePath(s);
        expect(p.startsWith("/")).toBe(true);
        expect(p.startsWith("//")).toBe(false);
      }),
    );
  });
});

describe("matchRoute", () => {
  it("matches every declared route, with or without a trailing slash", () => {
    for (const r of ROUTES) {
      expect(matchRoute(r)).toBe(r);
      if (r !== "/") expect(matchRoute(`${r}/`)).toBe(r);
    }
  });

  it("returns null for unknown paths", () => {
    expect(matchRoute("/planning")).toBeNull();
    expect(matchRoute("/research/extra")).toBeNull();
  });
});

describe("legacyRedirectTarget", () => {
  it("maps each old hash link on the root to its new path", () => {
    expect(legacyRedirectTarget("/", "#privacy")).toBe("/privacy");
    expect(legacyRedirectTarget("/", "#terms")).toBe("/terms");
    expect(legacyRedirectTarget("/", "#contact")).toBe("/contact");
  });

  it("every redirect target is a real route", () => {
    for (const target of Object.values(LEGACY_HASH_REDIRECTS)) {
      expect(matchRoute(target)).toBe(target);
    }
  });

  it("leaves home-page section anchors alone", () => {
    for (const h of ["#hero", "#projects", "#articles", "#about", "", "#"]) {
      expect(legacyRedirectTarget("/", h)).toBeNull();
    }
  });

  it("does not redirect a hash on any other page", () => {
    expect(legacyRedirectTarget("/research", "#contact")).toBeNull();
  });
});
