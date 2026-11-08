import { useState } from "react";
import {
  ButtonLink,
  CodeBlock,
  PageHeader,
  Section,
  StatTile,
} from "../components/ui";
import {
  DEMO_VIDEO_EMBED_URL,
  HEADLINE_STATS,
  PAPER,
  arxivUrl,
  paperBibtex,
} from "../data/site";
import DemoVideo from "../components/DemoVideo";

const METHOD_STEPS = [
  {
    step: "Pass 1",
    title: "Map the document's depths",
    body: "The model reads a sample of the document's layout and decides how many levels of nesting it uses, and what each level looks like in this particular document.",
  },
  {
    step: "Pass 2",
    title: "Classify every element by position",
    body: "Each heading and standard is placed on that depth map by where it sits, not by what it is called. \"Strand 1:\" and \"Benchmark 1.1\" can be the same level in two states, or different levels.",
  },
  {
    step: "Parse",
    title: "Resolve into one schema",
    body: "A separate step turns the detected hierarchy into one canonical record per standard, with a stable identifier, so every state can be queried the same way.",
  },
];

export default function ResearchPage() {
  const url = arxivUrl();
  return (
    <>
      <PageHeader
        eyebrow="Research"
        title="Recovering the structure of early learning standards"
        lede="Every US state publishes early learning standards, and each designs its own document. Software cannot read them as they are. This research shows how a language model can recover their structure reliably enough to build on."
      >
        {url ? (
          <ButtonLink href={url} external>
            Read the paper on arXiv
          </ButtonLink>
        ) : (
          <span className="inline-flex items-center rounded-md border border-dashed border-border px-4 py-2 text-sm text-muted-foreground">
            Preprint forthcoming on arXiv
          </span>
        )}
        <ButtonLink href="/data" variant="secondary">
          See the data
        </ButtonLink>
      </PageHeader>

      <Section title="The problem in plain language">
        <p>
          A standard such as "engages in an activity for a sustained period of
          time" only means something in context: which skill area it belongs
          to, and which goal inside that area. In a PDF that context is carried
          by layout and labels, and every state uses different ones. Arizona
          writes "Strand 1:", Kentucky writes "Benchmark 1.1", Nevada's
          numbering skips a level, and Colorado has no sub-strand level at all.
        </p>
        <p>
          The hard part is not reading the words. It is recovering where each
          standard sits in its hierarchy, because the clues that reveal that
          are exactly what varies from state to state.
        </p>
      </Section>

      <Section title="The method" wide>
        <ol className="grid gap-4 md:grid-cols-3">
          {METHOD_STEPS.map((s, i) => (
            <li
              key={s.step}
              className="relative rounded-lg border border-border bg-background p-6 shadow-sm"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                {s.step}
              </p>
              <h3 className="mt-1 text-lg font-semibold text-foreground">
                {s.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {s.body}
              </p>
              {i < METHOD_STEPS.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-xl text-muted-foreground md:block"
                >
                  →
                </span>
              )}
            </li>
          ))}
        </ol>
        <p className="mt-4 text-sm">
          There is no state-specific code path: one set of instructions handles
          every document.
        </p>
      </Section>

      <Section title="Headline results" wide>
        <div className="grid gap-4 sm:grid-cols-3">
          {HEADLINE_STATS.map((s) => (
            <StatTile key={s.label} {...s} />
          ))}
        </div>
        <p className="text-sm">
          These are measured on an annotated subset of each state's document,
          the same subset the paper reports. The paper also reports where the
          method is not yet stable: repeated runs are not identical, and the
          instability is concentrated in three known places. One of the
          author's own earlier results did not reproduce, and the paper says
          so.
        </p>
      </Section>

      {DEMO_VIDEO_EMBED_URL && (
        <Section title="Demo">
          <DemoVideo src={DEMO_VIDEO_EMBED_URL} />
        </Section>
      )}

      {/* <Section title="Cite this work">
        <p className="text-sm">
          <span className="font-medium text-foreground">{PAPER.title}</span>.{" "}
          {PAPER.authors.join(", ")}, {PAPER.year}.
        </p>
        <BibtexBlock />
      </Section> */}
    </>
  );
}

function BibtexBlock() {
  const bib = paperBibtex();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(bib);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable: the text is still selectable */
    }
  };
  return (
    <div>
      <CodeBlock label="BibTeX">{bib}</CodeBlock>
      <button
        type="button"
        onClick={copy}
        className="mt-2 text-sm font-medium text-primary hover:underline"
      >
        {copied ? "Copied" : "Copy BibTeX"}
      </button>
    </div>
  );
}
