import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="flex flex-col gap-16 py-8">
      {/* Hero */}
      <section className="max-w-3xl mx-auto text-center">
        <h2 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          Parent Planning Tool
        </h2>
        <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
          Create personalized early learning plans for your child, grounded in
          real state-specific standards. Our conversational planning assistant
          helps you build actionable, evidence-based activities tailored to your
          child's interests and needs.
        </p>
        <Link
          to="/planning"
          className="mt-8 inline-block rounded-md bg-primary px-8 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Start Planning
        </Link>
      </section>

      {/* How It Works */}
      <section className="max-w-4xl mx-auto w-full">
        <h3 className="text-2xl font-semibold text-foreground text-center mb-8">
          How It Works
        </h3>
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="rounded-lg border bg-card p-6 text-center">
            <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold">
              1
            </div>
            <h4 className="font-medium text-card-foreground">
              Share About Your Child
            </h4>
            <p className="mt-2 text-sm text-muted-foreground">
              Tell us your child's name, age, state, interests, and any areas
              you'd like to focus on.
            </p>
          </div>
          <div className="rounded-lg border bg-card p-6 text-center">
            <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold">
              2
            </div>
            <h4 className="font-medium text-card-foreground">
              Get a Personalized Plan
            </h4>
            <p className="mt-2 text-sm text-muted-foreground">
              Our AI assistant generates activities linked to real early
              learning standards for your state.
            </p>
          </div>
          <div className="rounded-lg border bg-card p-6 text-center">
            <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold">
              3
            </div>
            <h4 className="font-medium text-card-foreground">
              Track &amp; Refine
            </h4>
            <p className="mt-2 text-sm text-muted-foreground">
              Save your plan, revisit it anytime, and refine it through
              conversation as your child grows.
            </p>
          </div>
        </div>
      </section>

      {/* Organization Info */}
      <section className="max-w-3xl mx-auto text-center">
        <h3 className="text-2xl font-semibold text-foreground mb-4">
          Early Learning Standards Platform
        </h3>
        <p className="text-muted-foreground leading-relaxed">
          The Parent Planning Tool is part of the Early Learning Standards
          Platform — an initiative to make state early learning standards
          accessible and actionable for families. We maintain a comprehensive
          database of standards across multiple states so every plan is grounded
          in real, evidence-based benchmarks. To learn more about the Early
          Learning Standards Platform or to contact us visit{" "}
          <a
            href="https://edtechco.org"
            target="_blank"
            className="text-primary"
          >
            edtechco.org
          </a>
        </p>
      </section>
    </div>
  );
}
