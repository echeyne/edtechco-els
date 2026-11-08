import { useEffect, type ReactNode } from "react";
import { clsx } from "clsx";
import { Link } from "../router";

export const SITE_NAME = "EdTech Co.";

/** Sets document.title for the lifetime of a page. */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    document.title = title ? `${title} | ${SITE_NAME}` : SITE_NAME;
  }, [title]);
}

export function PageHeader({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow?: string;
  title: string;
  lede?: ReactNode;
  children?: ReactNode;
}) {
  useDocumentTitle(title);
  return (
    <header className="mx-auto max-w-3xl px-4 pb-10 pt-16 text-center sm:pt-20">
      {eyebrow && (
        <p className="mb-3 text-sm font-semibold uppercase tracking-wide text-primary">
          {eyebrow}
        </p>
      )}
      <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
        {title}
      </h1>
      {lede && (
        <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
          {lede}
        </p>
      )}
      {children && (
        <div className="mt-8 flex flex-wrap justify-center gap-3">{children}</div>
      )}
    </header>
  );
}

export function Section({
  id,
  title,
  children,
  wide = false,
  className,
}: {
  id?: string;
  title?: string;
  children: ReactNode;
  wide?: boolean;
  className?: string;
}) {
  return (
    <section
      id={id}
      className={clsx(
        "mx-auto px-4 pb-14",
        wide ? "max-w-6xl" : "max-w-3xl",
        className,
      )}
    >
      {title && (
        <h2 className="mb-5 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          {title}
        </h2>
      )}
      <div className="space-y-4 leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}

const buttonBase =
  "inline-flex items-center justify-center gap-1 rounded-md px-4 py-2 text-sm font-medium shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2";

export function ButtonLink({
  href,
  children,
  variant = "primary",
  external = false,
  download,
}: {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
  external?: boolean;
  download?: boolean;
}) {
  const className = clsx(
    buttonBase,
    variant === "primary"
      ? "bg-primary text-primary-foreground hover:bg-primary/90"
      : "border border-border bg-background text-foreground hover:bg-accent",
  );
  if (external || download) {
    return (
      <a
        href={href}
        className={className}
        download={download || undefined}
        {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      >
        {children}
        {external && <span aria-hidden="true">↗</span>}
      </a>
    );
  }
  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}

export function Card({
  title,
  children,
  className,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-lg border border-border bg-background p-6 shadow-sm",
        className,
      )}
    >
      {title && (
        <h3 className="mb-2 text-lg font-semibold text-foreground">{title}</h3>
      )}
      <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </div>
  );
}

export function StatTile({
  value,
  label,
  detail,
}: {
  value: string;
  label: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-6 text-center shadow-sm">
      <p className="text-4xl font-bold tracking-tight text-foreground">
        {value}
      </p>
      <p className="mt-2 text-sm font-semibold text-foreground">{label}</p>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        {detail}
      </p>
    </div>
  );
}

/** A labelled pre block for code, JSON and BibTeX. */
export function CodeBlock({
  label,
  wrap = false,
  children,
}: {
  label?: string;
  /** Wrap long lines instead of scrolling sideways. */
  wrap?: boolean;
  children: string;
}) {
  return (
    <figure className="overflow-hidden rounded-lg border border-border bg-secondary">
      {label && (
        <figcaption className="border-b border-border px-4 py-2 text-xs font-medium text-muted-foreground">
          {label}
        </figcaption>
      )}
      <pre
        className={clsx(
          "p-4 text-xs leading-relaxed text-foreground",
          wrap ? "whitespace-pre-wrap break-words" : "overflow-x-auto",
        )}
      >
        <code>{children}</code>
      </pre>
    </figure>
  );
}

/** Link to /contact with the reason dropdown preselected. */
export function contactHref(reason: string) {
  return `/contact?reason=${encodeURIComponent(reason)}`;
}
