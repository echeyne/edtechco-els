import { Link } from "../router";
import { StatTile } from "./ui";
import { HEADLINE_STATS } from "../data/site";
import { coverage } from "../data/coverage";

const [RECALL, AUDITED, HALLUCINATED] = HEADLINE_STATS;
const LOADED_STATES = coverage.filter((s) => s.status !== "planned").length;

/** Home-page evidence strip. Every number comes from data/site.ts or data/coverage.ts. */
export default function HomeProof() {
  return (
    <section id="evidence" className="mx-auto max-w-5xl px-4 pb-16">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile
          value={RECALL.value}
          label={RECALL.label}
          detail={RECALL.detail}
        />
        <StatTile
          value={`${HALLUCINATED.value} in ${AUDITED.value}`}
          label="Hallucinated elements in a hand audit"
          detail={AUDITED.detail}
        />
        <StatTile
          value={String(LOADED_STATES)}
          label="States in the Explorer"
          detail="as partial previews for now; full documents are added state by state"
        />
      </div>
      <p className="mt-6 text-center text-sm">
        <Link
          href="/research"
          className="font-medium text-primary transition-colors hover:text-primary/80"
        >
          How these were measured →
        </Link>
      </p>
    </section>
  );
}
