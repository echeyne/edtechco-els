import { ButtonLink, CodeBlock } from "./ui";
import { EXPLORER_URL } from "../data/site";

/**
 * The same Arizona record /data shows in full
 * (outputs/08-26-26/AZ-parsing.json, US-AZ-2018-LL.1.1.a), cut down to its
 * codes and names.
 */
const AZ_EXCERPT = `{
  "standard_id": "US-AZ-2018-LL.1.1.a",
  "domain":     { "code": "LL",     "name": "Language and Literacy" },
  "strand":     { "code": "LL.1",   "name": "Language" },
  "sub_strand": { "code": "LL.1.1", "name": "Receptive Language Understanding" },
  "indicator":  {
    "code": "LL.1.1.a",
    "name": "Demonstrates understanding of a variety of finger-plays, rhymes, chants and songs, poems, conversations, and stories."
  }
}`;

export default function HomeExample() {
  return (
    <section id="example" className="mx-auto max-w-6xl px-4 pb-16">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          From a PDF page to structured records
        </h2>
        <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
          Arizona prints this table on page 67 of its 2018 standards. The
          dataset turns it into three records, one per lettered indicator,
          each with every level above it coded.
        </p>
      </div>

      <div className="mt-10 grid grid-cols-1 items-center gap-6 lg:grid-cols-2">
        <figure className="overflow-hidden rounded-lg border border-border bg-background shadow-sm">
          <img
            src="/images/az-language-concept-1.png"
            alt="Page 67 of Arizona's 2018 Early Learning Standards: Language and Literacy, Strand 1: Language, Concept 1: Receptive Language Understanding, and indicators a, b and c with examples."
            className="w-full"
            width={1424}
            height={1000}
            loading="lazy"
          />
          <figcaption className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
            The printed page
          </figcaption>
        </figure>
        <CodeBlock label="Indicator a, 1 of 3 records from this page" wrap>
          {AZ_EXCERPT}
        </CodeBlock>
      </div>

      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <ButtonLink href="/data">What the data looks like</ButtonLink>
        <ButtonLink href={EXPLORER_URL} variant="secondary" external>
          Open the Explorer
        </ButtonLink>
      </div>
    </section>
  );
}
