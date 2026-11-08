import { contactHref } from "../components/ui";
import { Link } from "../router";
import { EXPLORER_URL } from "../data/site";
import { coverage } from "../data/coverage";
import AudiencePage from "./AudiencePage";

export default function ForStatesPage() {
  const loaded = coverage
    .filter((s) => s.status !== "planned")
    .map((s) => s.name);
  return (
    <AudiencePage
      eyebrow="For state agencies"
      title="Your standards, ready for the systems that use them"
      lede="Quality rating systems, curriculum reviews and P-3 alignment all start by mapping something to your early learning standards. Today that mapping is done by hand from a PDF, every time."
      primaryCta={{
        label: "Validate your state's data",
        href: contactHref("validate-state"),
      }}
      secondaryCta={{
        label: "Find your state in the Explorer",
        href: EXPLORER_URL,
        external: true,
      }}
      problemTitle="Where the PDF gets in the way"
      problems={[
        {
          title: "QRIS and curriculum review",
          body: "Programs and publishers are asked to show alignment to your standards. Each one rebuilds the same list by copying from the document.",
        },
        {
          title: "P-3 alignment",
          body: "Connecting early learning standards to kindergarten and early grades standards needs both sides in a form that can be lined up, not just read.",
        },
        {
          title: "Revisions",
          body: "When the standards are revised, every downstream crosswalk built from the old PDF goes quietly out of date.",
        },
      ]}
      offerTitle="What the platform provides"
      offers={[
        {
          title: "Every standard as a record",
          body: "Each indicator with its domain, strand and sub-strand, a stable ID, and the page it came from.",
        },
        {
          title: "Traceable to the source",
          body: "Every record links back to its page in your published PDF, so any value can be checked in seconds.",
        },
        {
          title: "Comparable across states",
          body: "One schema for every state, so your standards can be compared directly with other states'.",
        },
      ]}
      example={{
        title: "Your state in the Explorer",
        body: (
          <>
            <p>
              The Explorer currently includes {loaded.join(", ")}, each as a
              partial preview while full documents are processed and reviewed.{" "}
              <Link
                href="/data"
                className="font-medium text-primary hover:underline"
              >
                See what each record contains
              </Link>
              .
            </p>
            <p>
              If your state is not listed yet, you can{" "}
              <Link
                href={contactHref("request-state")}
                className="font-medium text-primary hover:underline"
              >
                request it
              </Link>
              .
            </p>
          </>
        ),
      }}
      ask={{
        title: "Validate your state's data",
        body: "The most useful thing a standards coordinator can do is check a sample of your state's records against your own document. You'll get a link to the records, each tied to its source page, and every correction goes back into the data.",
        cta: {
          label: "Request a validation",
          href: contactHref("validate-state"),
        },
      }}
    />
  );
}
