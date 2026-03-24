import {
  Brain,
  FileSearch,
  Layers,
  MessageSquare,
  ShieldCheck,
  Database,
  Workflow,
  Sparkles,
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
          About the ELS Project
        </h2>
        <p className="mt-2 text-muted-foreground">
          The Early Learning Standards (ELS) platform uses AI at every layer
          &mdash; from extracting structured data out of state PDF documents, to
          powering a conversational planning assistant for parents. Here&rsquo;s
          how it all fits together.
        </p>
      </div>

      {/* AI Extraction Pipeline */}
      <Section icon={FileSearch} title="AI-Powered Document Extraction">
        <p>
          State early learning standards are published as PDFs with widely
          varying formats. We run a multi-stage pipeline that turns those
          documents into structured, queryable data:
        </p>
        <ol className="space-y-2 pt-1" role="list">
          <PipelineStep
            number={1}
            label="Ingestion"
            detail="Source PDFs are uploaded to S3 and versioned for traceability."
          />
          <PipelineStep
            number={2}
            label="Text Extraction (AWS Textract)"
            detail="Each page is processed by Amazon Textract to produce text blocks with page numbers and reading-order metadata."
          />
          <PipelineStep
            number={3}
            label="Structure Detection (Claude on Bedrock)"
            detail="Text blocks are chunked and sent to Claude via Amazon Bedrock. A detailed prompt instructs the model to identify domains, strands, sub-strands, and indicators by nesting depth — not by the labels each state happens to use."
          />
          <PipelineStep
            number={4}
            label="Hierarchy Parsing"
            detail="Detected elements are assembled into a normalized four-level hierarchy (Domain → Strand → Sub-Strand → Indicator) and persisted to a relational database."
          />
          <PipelineStep
            number={5}
            label="Human Verification"
            detail="Every extracted record carries a confidence score. Reviewers use this Explorer app to verify, edit, or flag items before they're used downstream."
          />
        </ol>
      </Section>

      {/* LLM Structure Detection */}
      <Section icon={Brain} title="LLM-Driven Structure Detection">
        <p>
          The hardest part of the pipeline is understanding each state&rsquo;s
          unique document layout. Claude receives a carefully engineered prompt
          that:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Classifies elements by their nesting depth rather than
            state-specific labels (e.g., a state&rsquo;s &ldquo;Goal&rdquo;
            might map to our &ldquo;Strand&rdquo; level).
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
          states and power the planning assistant with a uniform query
          interface.
        </p>
      </Section>

      {/* Planning Assistant */}
      <Section icon={MessageSquare} title="Conversational Planning Assistant">
        <p>
          The parent-facing Planning Tool is powered by an AI agent built with
          the Strands framework running on Amazon Bedrock AgentCore. It uses
          Claude Sonnet as its foundation model and follows a guided multi-step
          conversation:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Collects the child&rsquo;s name, state, and age range through
            natural dialogue.
          </li>
          <li>
            Queries the standards database in real time using tool-calling to
            fetch available states, age ranges, and matching indicators.
          </li>
          <li>
            Generates a personalized activity plan grounded in real indicators
            &mdash; every suggested activity references a specific standard
            code.
          </li>
          <li>
            Persists plans to the database and supports follow-up refinement
            sessions without re-entering profile information.
          </li>
          <li>
            Streams responses over WebSocket for a real-time chat experience.
          </li>
        </ul>
      </Section>

      {/* Agent Tool Use */}
      <Section icon={Workflow} title="Agent Tool Architecture">
        <p>
          The planning agent doesn&rsquo;t just generate text &mdash; it
          orchestrates real database operations through a set of tools:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            <span className="font-medium text-foreground">StandardsQuery</span>{" "}
            &mdash; retrieves available states, age ranges, and learning
            indicators from the RDS database via the Data API.
          </li>
          <li>
            <span className="font-medium text-foreground">PlanManagement</span>{" "}
            &mdash; creates, updates, retrieves, and deletes learning plans,
            storing structured JSON content alongside child profile metadata.
          </li>
        </ul>
        <p className="pt-1">
          The agent decides when and how to call these tools based on the
          conversation context, following a structured workflow defined in its
          system prompt.
        </p>
      </Section>

      {/* Safety & Guardrails */}
      <Section icon={ShieldCheck} title="Safety &amp; Guardrails">
        <p>
          The planning assistant is wrapped in Amazon Bedrock Guardrails that
          enforce content safety and privacy:
        </p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Content filters block harmful categories (violence, hate speech,
            misconduct) and prompt-injection attempts.
          </li>
          <li>
            Topic policies deny off-topic requests including medical advice,
            developmental diagnoses, politics, religion, and financial guidance.
          </li>
          <li>
            PII detection blocks emails, phone numbers, SSNs, credit card
            numbers, and other sensitive data from entering or leaving the
            model.
          </li>
          <li>Profanity filtering is enabled via managed word lists.</li>
        </ul>
        <p className="pt-1">
          Only the child&rsquo;s first name is ever collected &mdash; no last
          names, birthdates, or other identifying information.
        </p>
      </Section>

      {/* Infrastructure */}
      <Section icon={Database} title="Infrastructure">
        <p>The platform runs on AWS with a serverless-first architecture:</p>
        <ul className="list-disc space-y-1 pl-5 pt-1">
          <li>
            Amazon Bedrock for foundation model access (Claude) and guardrails.
          </li>
          <li>
            Bedrock AgentCore Runtime for hosting the Strands-based planning
            agent with WebSocket streaming.
          </li>
          <li>AWS Textract for OCR and document text extraction.</li>
          <li>
            Amazon RDS (PostgreSQL) via the Data API for standards and plan
            storage.
          </li>
          <li>S3 for raw PDF storage and intermediate pipeline artifacts.</li>
          <li>
            Lambda + API Gateway (Hono) for the Explorer and Planning APIs.
          </li>
          <li>CloudFront + S3 for frontend hosting.</li>
        </ul>
      </Section>

      {/* Built with AI */}
      <Section icon={Sparkles} title="Built with AI, Verified by Humans">
        <p>
          AI accelerates every step of this project &mdash; from extracting
          thousands of standards out of dense PDF documents, to generating
          personalized learning plans in real time. But every AI-produced record
          passes through a human verification layer before it influences a
          child&rsquo;s learning plan. The Explorer app you&rsquo;re using right
          now is that verification interface.
        </p>
      </Section>
    </div>
  );
}
