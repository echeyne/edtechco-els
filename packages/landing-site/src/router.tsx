/**
 * A minimal path router (History API). The site is small enough that a
 * dependency is not worth it: one external store holding the current URL, a
 * `<Link>` that intercepts plain left-clicks, and a legacy-hash redirect.
 *
 * Deep paths work in production because the CloudFront distribution maps
 * S3's 403/404 back to /index.html with a 200
 * (infra/cdk/lib/landing-site-stack.ts, customErrorResponses).
 */
import {
  useSyncExternalStore,
  type AnchorHTMLAttributes,
  type MouseEvent,
} from "react";

export const ROUTES = [
  "/",
  "/research",
  "/data",
  "/for-states",
  "/for-researchers",
  "/for-curriculum",
  "/about",
  "/brief",
  "/contact",
  "/privacy",
  "/terms",
] as const;

export type RoutePath = (typeof ROUTES)[number];

/**
 * The site used hash routing until 2026-11. Links already sent out (emails,
 * Medium articles) point at these, so each one is redirected rather than
 * dropped. Home-page section anchors (#hero, #evidence, #example, #articles,
 * #about) are NOT in this map: they are in-page anchors on "/". The old
 * #projects anchor is gone; it now just opens the top of the home page.
 */
export const LEGACY_HASH_REDIRECTS: Record<string, RoutePath> = {
  "#privacy": "/privacy",
  "#terms": "/terms",
  "#contact": "/contact",
};

/** Strip a trailing slash (except on root) and lowercase the path. */
export function normalizePath(pathname: string): string {
  // Strip whitespace and slashes from both ends in one pass: trimming before
  // dropping a trailing slash would leave "a /" as "/a ", which is not stable.
  const inner = pathname
    .toLowerCase()
    .replace(/^[\s/]+|[\s/]+$/g, "")
    .replace(/\/{2,}/g, "/");
  return `/${inner}`;
}

/** Resolve a pathname to a known route, or null for a 404. */
export function matchRoute(pathname: string): RoutePath | null {
  const p = normalizePath(pathname);
  return (ROUTES as readonly string[]).includes(p) ? (p as RoutePath) : null;
}

/**
 * Where an old hash link should land, or null if it is not a legacy link.
 * Only applies on the root path: `/research#foo` is a real in-page anchor.
 */
export function legacyRedirectTarget(
  pathname: string,
  hash: string,
): RoutePath | null {
  if (normalizePath(pathname) !== "/") return null;
  return LEGACY_HASH_REDIRECTS[hash.toLowerCase()] ?? null;
}

// ---------------------------------------------------------------------------
// Location store
// ---------------------------------------------------------------------------

export interface Location {
  pathname: string;
  search: string;
  hash: string;
}

const listeners = new Set<() => void>();
let snapshot: Location = readLocation();

function readLocation(): Location {
  const { pathname, search, hash } = window.location;
  return { pathname, search, hash };
}

function emit() {
  const next = readLocation();
  if (
    next.pathname !== snapshot.pathname ||
    next.search !== snapshot.search ||
    next.hash !== snapshot.hash
  ) {
    snapshot = next;
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("popstate", emit);
  window.addEventListener("hashchange", emit);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      window.removeEventListener("popstate", emit);
      window.removeEventListener("hashchange", emit);
    }
  };
}

export function useLocation(): Location {
  return useSyncExternalStore(subscribe, () => snapshot);
}

/** Push (or replace) a same-origin URL and notify subscribers. */
export function navigate(to: string, opts: { replace?: boolean } = {}) {
  if (opts.replace) window.history.replaceState(null, "", to);
  else window.history.pushState(null, "", to);
  emit();
}

/**
 * Rewrite a legacy hash URL in place. Called once at startup, before the
 * first render, so the old URL never renders the home page first.
 */
export function applyLegacyRedirect(): RoutePath | null {
  const target = legacyRedirectTarget(
    window.location.pathname,
    window.location.hash,
  );
  if (target) navigate(target, { replace: true });
  return target;
}

/** Test hook: re-read window.location after a test mutates it. */
export function resyncLocation() {
  emit();
}

// ---------------------------------------------------------------------------
// <Link>
// ---------------------------------------------------------------------------

function isInternal(href: string) {
  return href.startsWith("/") && !href.startsWith("//");
}

export interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  href: string;
}

/**
 * An `<a>` that navigates client-side for internal paths. Modified clicks
 * (new tab, etc.), external URLs and `target` links fall through to the
 * browser untouched.
 */
export function Link({ href, onClick, target, ...rest }: LinkProps) {
  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (
      e.defaultPrevented ||
      e.button !== 0 ||
      e.metaKey ||
      e.ctrlKey ||
      e.shiftKey ||
      e.altKey ||
      target ||
      !isInternal(href)
    ) {
      return;
    }
    e.preventDefault();
    const current =
      window.location.pathname + window.location.search + window.location.hash;
    if (current !== href) navigate(href);
    else if (href.includes("#")) scrollToHash(href.slice(href.indexOf("#")));
  };
  return <a href={href} target={target} onClick={handleClick} {...rest} />;
}

export function scrollToHash(hash: string) {
  if (!hash || hash === "#") return false;
  const el = document.getElementById(decodeURIComponent(hash.slice(1)));
  if (!el) return false;
  el.scrollIntoView?.({ behavior: "smooth", block: "start" });
  return true;
}
