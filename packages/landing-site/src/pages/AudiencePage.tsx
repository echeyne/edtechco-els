import type { ReactNode } from "react";
import { ButtonLink, Card, PageHeader, Section } from "../components/ui";

export interface AudiencePageProps {
  eyebrow: string;
  title: string;
  lede: string;
  primaryCta: { label: string; href: string; external?: boolean };
  secondaryCta?: { label: string; href: string; external?: boolean };
  problemTitle: string;
  problems: { title: string; body: string }[];
  offerTitle: string;
  offers: { title: string; body: string }[];
  /** Optional: only for a page with a real, finished example to show. */
  example?: { title: string; body: ReactNode };
  ask: { title: string; body: string; cta: { label: string; href: string } };
}

/** Shared layout for /for-states, /for-researchers and /for-curriculum. */
export default function AudiencePage(p: AudiencePageProps) {
  return (
    <>
      <PageHeader eyebrow={p.eyebrow} title={p.title} lede={p.lede}>
        <ButtonLink href={p.primaryCta.href} external={p.primaryCta.external}>
          {p.primaryCta.label}
        </ButtonLink>
        {p.secondaryCta && (
          <ButtonLink
            href={p.secondaryCta.href}
            external={p.secondaryCta.external}
            variant="secondary"
          >
            {p.secondaryCta.label}
          </ButtonLink>
        )}
      </PageHeader>

      <Section title={p.problemTitle} wide>
        <div className="grid gap-4 md:grid-cols-3">
          {p.problems.map((x) => (
            <Card key={x.title} title={x.title}>
              <p>{x.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title={p.offerTitle} wide>
        <div className="grid gap-4 md:grid-cols-3">
          {p.offers.map((x) => (
            <Card key={x.title} title={x.title}>
              <p>{x.body}</p>
            </Card>
          ))}
        </div>
      </Section>

      {p.example && (
        <Section title={p.example.title}>{p.example.body}</Section>
      )}

      <Section>
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-foreground">
            {p.ask.title}
          </h2>
          <p className="mx-auto mt-3 max-w-xl">{p.ask.body}</p>
          <div className="mt-6">
            <ButtonLink href={p.ask.cta.href}>{p.ask.cta.label}</ButtonLink>
          </div>
        </div>
      </Section>
    </>
  );
}
