/**
 * Site-wide facts that several pages quote. Keep every number here in step
 * with the paper (paper/main.tex, paper/arxiv_abstract.txt): nothing public
 * should contradict it.
 */

export const EXPLORER_URL = "https://els-explorer.edtechco.org";
export const CONTACT_EMAIL = "info@edtechco.org";

export const PAPER = {
  title:
    "Classify by Position, Not by Label: LLM-Driven Extraction of Hierarchical Structure from Fragmented US Early Learning Standards",
  authors: ["Emily Cheyne"],
  year: 2026,
  /**
   * Set once arXiv v1 is posted (e.g. "2611.01234"). While null, the
   * research page says the preprint is forthcoming and shows no link.
   */
  arxivId: null as string | null,
  primaryClass: "cs.CL",
};

export function arxivUrl(id: string | null = PAPER.arxivId): string | null {
  return id ? `https://arxiv.org/abs/${id}` : null;
}

export function paperBibtex(id: string | null = PAPER.arxivId): string {
  const lines = [
    `@misc{cheyne${PAPER.year}classify,`,
    `  title         = {${PAPER.title}},`,
    `  author        = {${PAPER.authors.join(" and ")}},`,
    `  year          = {${PAPER.year}},`,
  ];
  if (id) {
    lines.push(
      `  eprint        = {${id}},`,
      `  archivePrefix = {arXiv},`,
      `  primaryClass  = {${PAPER.primaryClass}},`,
      `  url           = {https://arxiv.org/abs/${id}},`,
    );
  } else {
    lines.push(`  note          = {Preprint, forthcoming on arXiv},`);
  }
  lines.push("}");
  return lines.join("\n");
}

/** Headline results, worded as the abstract words them. */
export const HEADLINE_STATS = [
  {
    value: "1.000",
    label: "Detector recall",
    detail:
      "at every hierarchy level, in all six annotated states (four development, two held out for validation)",
  },
  {
    value: "297",
    label: "Detections audited by hand",
    detail: "every in-scope detection on the annotated subset, checked manually",
  },
  {
    value: "1",
    label: "Hallucinated element",
    detail: "found by that audit, out of 297",
  },
] as const;

/**
 * Embed URL for the 2-3 minute demo video. While null, no video block
 * renders.
 */
export const DEMO_VIDEO_EMBED_URL: string | null = null;
