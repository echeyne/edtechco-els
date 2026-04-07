import {
  Brain,
  FileSearch,
  Layers,
  CheckCircle,
  Database,
  Sparkles,
  ExternalLink,
} from "lucide-react";

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

function PipelineStep({
  number,
  label,
  detail,
}: {
  number: number;
  label: string;
  detail: string;
}) {
  return (
    <li className="flex gap-3">
      <span
        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary"
        aria-hidden="true"
      >
        {number}
      </span>
      <div>
        <span className="font-medium text-foreground">{label}</span>
        <span className="ml-1">&mdash; {detail}</span>
      </div>
    </li>
  );
}

export default function InfoPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-12">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">
          About the ELS Explorer
        </h2>
        <p className="mt-2 text-muted-foreground">
          The ELS Explorer is the verification and browsing interface for the
          Early Learning Standards Pipeline. It lets reviewers inspect, edit,
          and approve the structured data that the pipeline extracts from state
          PDF documents. For more about the broader Early Learning Standards
          Platform, visit{" "}
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
      </div>

      {/* What the Explorer Does */}
      <Section icon={CheckCircle} title="What the Explorer Does">
        <p>
          The Explorer is the human-in-the-loop layer of the pipeline. After AI
          extraction produces structured records, reviewers use this app to:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Browse extracted domains, strands, sub-strands, and indicators for
            any processed state document.
          </li>
          <li>
            Compare the original source PDF with extracted data to verify
            accuracy.
          </li>
          <li>
            Edit or flag records that need correction before they enter the
            shared standards database.
          </li>
          <li>
            Review confidence scores assigned during extraction to prioritize
            which records need attention.
          </li>
        </ul>
      </Section>

      {/* AI Extraction Pipeline */}
      <Section icon={FileSearch} title="The Extraction Pipeline">
        <p>
          State early learning standards are published as PDFs with widely
          varying formats. The pipeline turns those documents into structured,
          queryable data through several stages:
        </p>
        <ol className="space-y-2 pt-1" role="list">
          <PipelineStep
            number={1}
            label="Ingestion"
            detail="Source PDFs are uploaded and versioned in S3 for traceability."
          />
          <PipelineStep
            number={2}
            label="Text Extraction"
            detail="Amazon Textract processes each page to produce text blocks with page numbers and reading-order metadata."
          />
          <PipelineStep
            number={3}
            label="Structure Detection"
            detail="Text blocks are chunked and sent to Claude via Amazon Bedrock. A detailed prompt instructs the model to identify domains, strands, sub-strands, and indicators by nesting depth — not by the labels each state happens to use."
          />
          <PipelineStep
            number={4}
            label="Hierarchy Assembly"
            detail="A second Claude pass validates and assembles detected elements into a normalized four-level hierarchy, resolving ambiguous nesting and merging cross-chunk fragments before persisting to the database."
          />
          <PipelineStep
            number={5}
            label="Human Verification"
            detail="Every extracted record carries a confidence score. Reviewers use this Explorer app to verify, edit, or flag items before they are used downstream."
          />
        </ol>
      </Section>

      {/* LLM Structure Detection */}
      <Section icon={Brain} title="LLM-Driven Structure Detection">
        <p>
          The hardest part of the pipeline is understanding each state&rsquo;s
          unique document layout. The LLM receives a carefully engineered prompt
          that:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Classifies elements by nesting depth rather than state-specific
            labels (e.g., a state&rsquo;s &ldquo;Goal&rdquo; might map to our
            &ldquo;Strand&rdquo; level).
          </li>
          <li>
            Distinguishes true indicators from illustrative examples or
            observable behaviors listed beneath them.
          </li>
          <li>
            Handles side-by-side age-group columns, extracting each as a
            separate indicator.
          </li>
          <li>
            Processes documents in overlapping chunks so elements that span page
            boundaries are never lost.
          </li>
          <li>
            Returns structured JSON with confidence scores, source page numbers,
            and verbatim source text for auditability.
          </li>
        </ul>
      </Section>

      {/* Normalized Data Model */}
      <Section icon={Layers} title="Normalized Data Model">
        <p>
          Regardless of how a state organizes its standards, every document is
          mapped into a consistent four-level hierarchy:
        </p>
        <div className="mt-2 flex items-center gap-2 text-xs font-medium">
          <span className="rounded bg-primary/10 px-2 py-1 text-primary">
            Domain
          </span>
          <span aria-hidden="true">→</span>
          <span className="rounded bg-primary/10 px-2 py-1 text-primary">
            Strand
          </span>
          <span aria-hidden="true">→</span>
          <span className="rounded bg-primary/10 px-2 py-1 text-primary">
            Sub-Strand
          </span>
          <span aria-hidden="true">→</span>
          <span className="rounded bg-primary/10 px-2 py-1 text-primary">
            Indicator
          </span>
        </div>
        <p className="pt-2">
          This normalization makes it possible to compare standards across
          states and powers downstream tools like the parent-facing Planning
          Tool with a uniform query interface.
        </p>
      </Section>

      {/* Infrastructure */}
      <Section icon={Database} title="Pipeline Infrastructure">
        <p>The extraction pipeline and Explorer run on AWS:</p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Amazon Bedrock for foundation model access (Claude) used in
            structure detection and hierarchy parsing.
          </li>
          <li>AWS Textract for OCR and document text extraction.</li>
          <li>
            Amazon RDS (PostgreSQL) via the Data API for standards storage.
          </li>
          <li>S3 for raw PDF storage and intermediate pipeline artifacts.</li>
          <li>Lambda + API Gateway for the Explorer API.</li>
          <li>CloudFront + S3 for frontend hosting.</li>
        </ul>
      </Section>

      {/* Built with AI */}
      <Section icon={Sparkles} title="Built with AI, Verified by Humans">
        <p>
          AI accelerates extraction of thousands of standards from dense PDF
          documents, but a human-in-the-loop verification is needed to ensure
          data quality and trust. This Explorer is that verification interface.
        </p>
      </Section>

      {/* Contact / More Info */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-5 text-sm text-muted-foreground">
        <p>
          The ELS Explorer is part of the Early Learning Standards Platform
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
    </div>
  );
}
