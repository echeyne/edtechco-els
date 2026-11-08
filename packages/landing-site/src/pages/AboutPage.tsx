import { PageHeader, Section } from "../components/ui";
import { Link } from "../router";
import {
  STATUS_LABEL,
  press,
  publications,
  talks,
} from "../data/publications";
import { articles } from "../data/articles";

const listItem =
  "rounded-lg border border-border bg-background p-5 shadow-sm";

export default function AboutPage() {
  return (
    <>
      <PageHeader eyebrow="About" title="Emily Cheyne" lede="Founder and independent researcher, EdTech Co." />

      <Section title="Bio">
        <p>
          Emily's research focuses on how software engineering and AI can
          improve early learning outcomes and inform public policy. Her current
          work builds pipelines that turn US state early learning standards
          into machine-readable data, and the Early Learning Standards Explorer
          that puts that data in front of educators, researchers and
          policymakers.
        </p>
        <p>
          She is a senior software engineer and holds a degree in Computer
          Science with a minor in Data Science from the University of British
          Columbia.
        </p>
        <p>
          <a
            href="mailto:emily@edtechco.org"
            className="font-medium text-primary hover:underline"
          >
            emily@edtechco.org
          </a>
        </p>
      </Section>

      <Section title="Publications">
        <ul className="space-y-3">
          {publications.map((p) => (
            <li key={p.title} className={listItem}>
              <p className="font-semibold text-foreground">
                {p.url ? (
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                  >
                    {p.title}
                  </a>
                ) : (
                  p.title
                )}
              </p>
              <p className="mt-1 text-sm">
                {p.authors.join(", ")}. {p.venue}, {p.year}.{" "}
                <span className="ml-1 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-foreground">
                  {STATUS_LABEL[p.status]}
                </span>
              </p>
              <p className="mt-2 text-sm">
                <Link href="/research" className="text-primary hover:underline">
                  {/* Summary and citation */}
                  Summary
                </Link>
              </p>
            </li>
          ))}
        </ul>
      </Section>

      {talks.length > 0 && (
        <Section title="Talks">
          <ul className="space-y-3">
            {talks.map((t) => (
              <li key={`${t.event}-${t.date}`} className={listItem}>
                <p className="font-semibold text-foreground">{t.title}</p>
                <p className="mt-1 text-sm">
                  {t.event}, {formatDate(t.date)}
                  {t.url && (
                    <>
                      {" · "}
                      <a
                        href={t.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        Link
                      </a>
                    </>
                  )}
                </p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {press.length > 0 && (
        <Section title="Press">
          <ul className="space-y-3">
            {press.map((m) => (
              <li key={m.url} className={listItem}>
                <a
                  href={m.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-foreground hover:underline"
                >
                  {m.title}
                </a>
                <p className="mt-1 text-sm">
                  {m.outlet}, {formatDate(m.date)}
                </p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section id="writing" title="Writing">
        <ul className="space-y-3">
          {articles.map((a) => (
            <li key={a.url} className={listItem}>
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-foreground hover:underline"
              >
                {a.title}
              </a>
              <p className="mt-1 text-sm">{a.description}</p>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function formatDate(iso: string) {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
