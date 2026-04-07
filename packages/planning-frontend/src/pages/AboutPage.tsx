import { Link } from "react-router-dom";
import { BookOpen, Layers, Sparkles, ExternalLink } from "lucide-react";

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-white p-5">
      <div className="mb-3 flex items-center gap-2 text-primary">
        <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
        <h3 className="text-base font-semibold">{title}</h3>
      </div>
      <div className="text-sm leading-relaxed text-muted-foreground space-y-2">
        {children}
      </div>
    </section>
  );
}

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-12">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          About the Planning Tool
        </h2>
        <p className="mt-2 text-muted-foreground">
          The Parent Planning Tool was created to help parents build
          personalized early learning plans grounded in state-specific
          standards. It is part of the Early Learning Standards Platform and
          uses a common standards database.
        </p>
      </div>

      {/* The Early Learning Standards Platform */}
      <Section icon={Layers} title="The Early Learning Standards Platform">
        <p>
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
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            edtechco.org
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        </p>
      </Section>

      {/* How the Planning Tool Fits In */}
      <Section icon={Sparkles} title="How the Planning Tool Fits In">
        <p>
          The Planning Tool sits on top of this standards database. When you
          create a plan, our AI assistant queries real indicators for your
          child's state and age, then generates activities that directly
          reference those standards. This means every suggestion in your plan is
          backed by the same benchmarks used by educators — not made up on the
          spot.
        </p>
      </Section>

      {/* Contact / More Info */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-5 text-sm text-muted-foreground">
        <p>
          The Planning Tool is part of the Early Learning Standards Platform
          built by EdTechCo. For general information about the project,
          partnership inquiries, or to get in touch, visit{" "}
          <a
            href="https://edtechco.org"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            edtechco.org
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        </p>
      </div>

      {/* Navigation */}
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
