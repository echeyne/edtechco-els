import { Link } from "react-router-dom";

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto py-8 flex flex-col gap-10">
      <section>
        <h2 className="text-3xl font-bold tracking-tight text-foreground">
          About the Planning Tool
        </h2>
        <p className="mt-4 text-muted-foreground leading-relaxed">
          The Parent Planning Tool was created to help parents build
          personalized early learning plans grounded in state-specific
          standards. It is part of the Early Learning Standards Platform and
          uses a common standards database.
        </p>
      </section>

      <section>
        <h3 className="text-xl font-semibold text-foreground mb-3">
          The Early Learning Standards Platform
        </h3>
        <p className="text-muted-foreground leading-relaxed">
          Early learning standards define what children should know and be able
          to do at various ages. Each state publishes its own set of standards,
          but they are often locked in PDFs and difficult for families to use.
          The Early Learning Standards Platform extracts, organizes, and
          verifies these standards into a searchable database — making them
          accessible to parents, educators, and tool builders alike. To learn
          more about the Early Learning Standards Platform or to contact us
          visit{" "}
          <a
            href="https://edtechco.org"
            target="_blank"
            className="text-primary"
          >
            edtechco.org
          </a>
        </p>
      </section>

      <section>
        <h3 className="text-xl font-semibold text-foreground mb-3">
          How the Planning Tool Fits In
        </h3>
        <p className="text-muted-foreground leading-relaxed">
          The Planning Tool sits on top of this standards database. When you
          create a plan, our AI assistant queries real indicators for your
          child's state and age, then generates activities that directly
          reference those standards. This means every suggestion in your plan is
          backed by the same benchmarks used by educators — not made up on the
          spot.
        </p>
      </section>

      <nav className="flex items-center gap-4 pt-2">
        <Link
          to="/"
          className="text-sm font-medium text-primary hover:underline"
        >
          ← Back to Home
        </Link>
        <span className="text-border">|</span>
        <Link
          to="/planning"
          className="text-sm font-medium text-primary hover:underline"
        >
          Go to Planning
        </Link>
      </nav>
    </div>
  );
}
