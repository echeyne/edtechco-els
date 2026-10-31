export default function AboutSection() {
  return (
    <section id="about" className="px-4 pb-16">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="mb-6 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Our Mission
        </h2>

        <p className="text-lg leading-relaxed text-muted-foreground sm:text-xl">
          At EdTech Co., we believe that data and technology can transform
          educational outcomes for young learners. Our mission goes beyond
          building tools — we are dedicated to making educational data
          accessible, actionable, and genuinely useful for the educators,
          parents, and policymakers who shape early learning experiences.
        </p>

        <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
          By focusing on early childhood education, we aim to bridge the gap
          between complex standards data and everyday decision-making, helping
          communities use evidence to give every child a stronger start.
        </p>

        <h3 className="mb-6 mt-12 text-2xl font-bold tracking-tight text-foreground">
          Our Team
        </h3>

        <div className="mx-auto max-w-md rounded-lg border border-border bg-background p-6 shadow-sm">
          <p className="text-lg font-semibold text-foreground">Emily Cheyne</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Founder & Independent Researcher, EdTech Co.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Emily's research
            focuses on how software engineering and AI can improve early
            learning outcomes and inform public policy, including building
            pipelines that turn state early learning standards into
            machine-readable data. She holds a degree in Computer Science with
            a minor in Data Science from the University of British Columbia.
          </p>
          <a
            href="mailto:emily@edtechco.org"
            className="mt-3 inline-block text-sm font-medium text-primary transition-colors hover:text-primary/80"
          >
            emily@edtechco.org
          </a>
        </div>
      </div>
    </section>
  );
}
