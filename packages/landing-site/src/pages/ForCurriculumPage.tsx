import { contactHref } from "../components/ui";
import AudiencePage from "./AudiencePage";

export default function ForCurriculumPage() {
  return (
    <AudiencePage
      eyebrow="For curriculum and edtech teams"
      title="Align to every state from one dataset"
      lede="A product sold nationally has to show alignment to each state's early learning standards. That usually means a separate crosswalk per state, each built by hand from a PDF."
      primaryCta={{
        label: "Register data-access interest",
        href: contactHref("curriculum-data"),
      }}
      secondaryCta={{ label: "See the data", href: "/data" }}
      problemTitle="The cost of alignment today"
      problems={[
        {
          title: "One crosswalk per state",
          body: "Each state's document has its own structure, so alignment work done for one state rarely carries over to the next.",
        },
        {
          title: "Revisions break it",
          body: "When a state revises its standards, existing crosswalks have to be found and redone.",
        },
        {
          title: "Hard to audit",
          body: "A crosswalk that cites standards by copied text, rather than a stable ID, is hard to check and hard to update.",
        },
      ]}
      offerTitle="What the data offers"
      offers={[
        {
          title: "Stable IDs to align against",
          body: "Map an activity or assessment item to a standard's ID once, and the link stays meaningful.",
        },
        {
          title: "The same shape for every state",
          body: "One schema across states, so an alignment tool written for one state works for the others.",
        },
        {
          title: "Source pages included",
          body: "Every record points to its page in the state's PDF, for reviewers who need to check.",
        },
      ]}
      ask={{
        title: "Pilot it on your alignment work",
        body: "If your team maintains state alignments, I'm looking for a small number of pilot partners. Tell me which states you align to and roughly how long it takes today.",
        cta: { label: "Ask about a pilot", href: contactHref("pilot") },
      }}
    />
  );
}
