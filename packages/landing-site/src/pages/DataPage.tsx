import { clsx } from "clsx";
import { Link } from "../router";
import {
  ButtonLink,
  CodeBlock,
  PageHeader,
  Section,
  contactHref,
} from "../components/ui";
import DemoVideo from "../components/DemoVideo";
import { COVERAGE_LABEL, coverage, type CoverageStatus } from "../data/coverage";
import { DEMO_VIDEO_EMBED_URL, EXPLORER_URL } from "../data/site";

/**
 * One real record: the pipeline's own output for Arizona's Language Strand,
 * Concept 1 (outputs/08-26-26/AZ-parsing.json, US-AZ-2018-LL.1.1.a), which
 * follows the conventions of evaluation/ground_truth_parser/AZ.json.
 * Descriptions are shortened for display, and source_page/source_text are
 * left out: source_page there counts pages of the 15-page subset PDF the run
 * used, not the printed page 67 the caption cites.
 */
const AZ_RECORD = `{
  "standard_id": "US-AZ-2018-LL.1.1.a",
  "country": "US",
  "state": "AZ",
  "version_year": 2018,
  "domain": {
    "code": "LL",
    "name": "Language and Literacy"
  },
  "strand": {
    "code": "LL.1",
    "name": "Language"
  },
  "sub_strand": {
    "code": "LL.1.1",
    "name": "Receptive Language Understanding",
    "description": "The child demonstrates understanding of directions, stories, conversations, and nonverbal cues.\\nReceptive language is the ability to understand or comprehend language that is heard or read. …"
  },
  "indicator": {
    "code": "LL.1.1.a",
    "name": "Demonstrates understanding of a variety of finger-plays, rhymes, chants and songs, poems, conversations, and stories.",
    "description": "Follows gestures and actions.\\nTeacher asks, \\"Where would you like to play? It's time to work.\\" …"
  },
  "age_band": "36-60"
}`;

const MAPPING = [
  {
    printed: "LANGUAGE AND LITERACY",
    level: "Domain",
    code: "LL",
    how: "abbreviated from the title",
  },
  {
    printed: "STRAND 1: LANGUAGE (printed twice)",
    level: "Strand",
    code: "LL.1",
    how: "the document's own number",
  },
  {
    printed: "Concept 1: Receptive Language Understanding",
    level: "Sub-strand",
    code: "LL.1.1",
    how: "the document's own number; the bold goal and the two paragraphs become its description",
  },
  {
    printed: "a. Demonstrates understanding of a variety of finger-plays, …",
    level: "Indicator",
    code: "LL.1.1.a",
    how: "the document's own letter; the bulleted examples become its description",
  },
  {
    printed: "b. Engages actively in finger-plays, …",
    level: "Indicator",
    code: "LL.1.1.b",
    how: "the document's own letter",
  },
  {
    printed: "c. Demonstrates understanding and follows directions …",
    level: "Indicator",
    code: "LL.1.1.c",
    how: "the document's own letter",
  },
];

/** What reading this one page correctly takes. Each point is true of the record above. */
const PAGE_CHALLENGES = [
  "The strand heading is printed twice, as the page title and again inside the table. It is one strand, not two.",
  "Arizona calls its third level a “Concept”. It is placed as the sub-strand by where it sits, not by what it is called.",
  "“Indicators and Examples in the Context of Daily Routines, Activities, and Play” is a column heading, not a level, so it creates no record.",
  "One table becomes three records, one per lettered indicator, each carrying the full chain of levels above it.",
  "The PDF's text runs words together (“andstories”, “Teacherextends”). The records have them separated.",
];

const SCHEMA_LEVELS = [
  {
    name: "Domain",
    note: "A broad area of development, such as Approaches to Learning or Language and Literacy.",
  },
  { name: "Strand", note: "A goal within the domain." },
  {
    name: "Sub-strand",
    note: "A narrower goal. Optional: some states, such as Colorado, have no level here.",
  },
  {
    name: "Indicator",
    note: "The observable standard itself. One record per indicator, with a stable ID.",
  },
];

const STATUS_STYLE: Record<CoverageStatus, string> = {
  full: "bg-primary text-primary-foreground",
  partial: "bg-secondary text-foreground border border-border",
  planned: "border border-dashed border-border text-muted-foreground",
};

export default function DataPage() {
  return (
    <>
      <PageHeader
        eyebrow="The data"
        title="What “machine-readable” means"
        lede="A standards PDF is written for people to read. The same standards as structured data can be searched, compared across states, and linked to curricula and assessments."
      >
        <ButtonLink href={EXPLORER_URL} external>
          Open the Explorer
        </ButtonLink>
        <ButtonLink href={contactHref("request-state")} variant="secondary">
          Request your state
        </ButtonLink>
      </PageHeader>

      <Section title="From a page to structured records" wide>
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <figure className="overflow-hidden rounded-lg border border-border bg-white shadow-sm">
            <img
              src="/images/az-language-concept-1.png"
              alt="Page 67 of Arizona's 2018 Early Learning Standards: a table headed Language and Literacy, Strand 1: Language, Concept 1: Receptive Language Understanding, a learning goal with two explanatory paragraphs, then indicators a, b and c, each with bulleted examples."
              className="w-full"
              width={1424}
              height={1000}
            />
            <figcaption className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
              Arizona Early Learning Standards (2018), page 67
            </figcaption>
          </figure>
          <CodeBlock label="Indicator a as a structured record (1 of 3 from this page)" wrap>
            {AZ_RECORD}
          </CodeBlock>
        </div>

        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="border-b border-border text-foreground">
              <tr>
                <th className="py-2 pr-4 font-semibold">Printed in the PDF</th>
                <th className="py-2 pr-4 font-semibold">Level</th>
                <th className="py-2 pr-4 font-semibold">Code</th>
                <th className="py-2 font-semibold">Where the code comes from</th>
              </tr>
            </thead>
            <tbody>
              {MAPPING.map((m) => (
                <tr key={m.code} className="border-b border-border/60">
                  <td className="py-2 pr-4">{m.printed}</td>
                  <td className="py-2 pr-4">{m.level}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-foreground">
                    {m.code}
                  </td>
                  <td className="py-2">{m.how}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="mb-2 font-semibold text-foreground">
            What reading this page takes
          </h3>
          <ul className="list-disc space-y-1 pl-6 text-sm">
            {PAGE_CHALLENGES.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
        <p className="text-sm">
          Every standard gets an ID of the form{" "}
          <code className="rounded bg-secondary px-1 text-foreground">
            country-state-year-code
          </code>
          , so the same standard always has the same ID.
        </p>
      </Section>

      <Section title="One schema for every state">
        <ol className="space-y-2">
          {SCHEMA_LEVELS.map((l, i) => (
            <li
              key={l.name}
              style={{ marginLeft: `${i * 1.25}rem` }}
              className="rounded-md border border-border bg-background px-4 py-3 shadow-sm"
            >
              <span className="font-semibold text-foreground">{l.name}</span>
              <span className="ml-2 text-sm">{l.note}</span>
            </li>
          ))}
        </ol>
        <p className="text-sm">
          Each record also carries the state, the document's year, an age band,
          and the page it came from, so any value can be checked against the
          original PDF.
        </p>
      </Section>

      <Section title="Coverage">
        <p>
          The Explorer currently holds a preview output for several states.
        </p>
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {coverage.map((s) => (
            <li
              key={s.code}
              className="flex items-center justify-between rounded-md border border-border bg-background px-4 py-3"
            >
              <span className="text-foreground">
                {s.name}
                {s.documentYear && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    {s.documentYear}
                  </span>
                )}
              </span>
              <span
                className={clsx(
                  "rounded-full px-2.5 py-0.5 text-xs font-medium",
                  STATUS_STYLE[s.status],
                )}
              >
                {COVERAGE_LABEL[s.status]}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-sm">
          Don't see your state?{" "}
          <Link
            href={contactHref("request-state")}
            className="font-medium text-primary hover:underline"
          >
            Request it
          </Link>
          .
        </p>
      </Section>

      {DEMO_VIDEO_EMBED_URL && (
        <Section title="Demo">
          <DemoVideo src={DEMO_VIDEO_EMBED_URL} />
        </Section>
      )}
    </>
  );
}
