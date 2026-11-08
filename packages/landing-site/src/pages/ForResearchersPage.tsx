import { contactHref } from "../components/ui";
import AudiencePage from "./AudiencePage";

export default function ForResearchersPage() {
  return (
    <AudiencePage
      eyebrow="For policy researchers"
      title="Compare states' expectations without rebuilding the dataset first"
      lede="Questions about what states expect of four-year-olds, and how those expectations differ, usually start with weeks of hand-coding PDFs. The structured data removes that step."
      primaryCta={{
        label: "Ask about data access",
        href: contactHref("research-data"),
      }}
      secondaryCta={{ label: "Read the research", href: "/research" }}
      problemTitle="Why cross-state work is slow"
      problems={[
        {
          title: "Every document is different",
          body: "States use different levels, labels and numbering, so a spreadsheet built for one state does not fit the next.",
        },
        {
          title: "Hand-coding does not scale",
          body: "Coding standards by hand is careful, slow work, and it has to be repeated whenever a state revises its document.",
        },
        {
          title: "Hard to reproduce",
          body: "Without a shared identifier for each standard, two studies of the same states are hard to line up.",
        },
      ]}
      offerTitle="What the data offers"
      offers={[
        {
          title: "One schema",
          body: "Domain, strand, sub-strand and indicator for every state, in the same fields.",
        },
        {
          title: "Stable IDs",
          body: "Each standard has a deterministic ID, so a result can cite exactly which standards it used.",
        },
        {
          title: "A documented method",
          body: "The extraction method and its measured accuracy, including where it is not yet stable, are written up in the paper.",
        },
      ]}
      ask={{
        title: "Working on early learning standards?",
        body: "If you are studying standards, alignment or early childhood data systems, I would like to hear what you need. Data access and collaboration are both open.",
        cta: { label: "Get in touch", href: contactHref("research-data") },
      }}
    />
  );
}
