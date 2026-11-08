import { useDocumentTitle, contactHref } from "../components/ui";
import { Link } from "../router";
import type { ReactNode } from "react";
import { CONTACT_EMAIL, EXPLORER_URL, arxivUrl } from "../data/site";
import { coverage } from "../data/coverage";

const SITE_ORIGIN = "https://edtechco.org";

/**
 * A one-page summary to link from cold emails instead of attaching a PDF.
 * Designed to print on a single Letter page: the navbar and footer are hidden
 * in print (`print:hidden`), and links are spelled out so they survive paper.
 */
export default function BriefPage() {
  useDocumentTitle("Brief: Early Learning Standards as Data");
  const loaded = coverage.filter((s) => s.status !== "planned").length;
  const paper = arxivUrl();

  return (
    <article className="mx-auto max-w-3xl px-4 py-12 text-[15px] leading-relaxed text-foreground print:max-w-none print:px-0 print:py-0 print:text-[11pt]">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">
            EdTech Co. · One-page brief
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight print:text-2xl">
            Every state's early learning standards, as structured data
          </h1>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          className="shrink-0 rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-accent print:hidden"
        >
          Print
        </button>
      </div>

      <BriefSection title="The problem">
        Every US state publishes early learning standards for children from
        birth to kindergarten, and each designs its own PDF. Quality rating
        systems, curriculum alignment, P-3 alignment and cross-state research
        all need those standards as data, so each organization rebuilds them by
        hand, one state at a time, and redoes the work whenever a state revises
        its document.
      </BriefSection>

      <BriefSection title="What it does">
        An AI pipeline reads each state's PDF, recovers its hierarchy (domain,
        strand, sub-strand, indicator), and stores every standard in one schema
        with a stable ID and a link to its source page. The public Explorer
        lets anyone browse the result and check it against the original. It
        currently holds {loaded} states as partial previews, with full
        documents being processed and reviewed.
      </BriefSection>

      <BriefSection title="Evidence it works">
        <ul className="mt-1 list-disc space-y-1 pl-5">
          <li>
            Detector recall of <strong>1.000</strong> at every hierarchy level,
            in all six annotated states.
          </li>
          <li>
            A manual audit of all <strong>297</strong> in-scope detections
            found <strong>one</strong> hallucinated element.
          </li>
          <li>
            Method and results written up as a research paper
            {paper ? (
              <>
                {" "}
                (<a href={paper} className="underline">{paper}</a>)
              </>
            ) : (
              ", forthcoming on arXiv"
            )}
            , including where the method is not yet stable.
          </li>
        </ul>
      </BriefSection>

      <BriefSection title="The ask">
        <ul className="mt-1 list-disc space-y-1 pl-5">
          <li>
            <strong>State agencies:</strong> check a sample of your state's
            records against your own document.
          </li>
          <li>
            <strong>Researchers:</strong> tell me what cross-state questions the
            data should answer.
          </li>
          <li>
            <strong>Curriculum and edtech teams:</strong> pilot it on one of
            your state alignments.
          </li>
        </ul>
      </BriefSection>

      <footer className="mt-8 border-t border-border pt-4 text-sm text-muted-foreground">
        <p>
          Emily Cheyne, EdTech Co. ·{" "}
          <a href={`mailto:${CONTACT_EMAIL}`} className="underline">
            {CONTACT_EMAIL}
          </a>
        </p>
        <p className="mt-1">
          Explorer:{" "}
          <a href={EXPLORER_URL} className="underline">
            {EXPLORER_URL.replace("https://", "")}
          </a>{" "}
          · More:{" "}
          <Link href="/research" className="underline">
            {SITE_ORIGIN.replace("https://", "")}/research
          </Link>
        </p>
        <p className="mt-3 print:hidden">
          <Link
            href={contactHref("general")}
            className="font-medium text-primary hover:underline"
          >
            Get in touch
          </Link>
        </p>
      </footer>
    </article>
  );
}

function BriefSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mb-5 break-inside-avoid">
      <h2 className="mb-1 text-lg font-semibold print:text-base">{title}</h2>
      <div className="text-muted-foreground print:text-foreground">
        {children}
      </div>
    </section>
  );
}
