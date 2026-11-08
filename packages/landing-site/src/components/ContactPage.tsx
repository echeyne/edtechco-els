import { useState, useRef, type FormEvent } from "react";
import { Link, useLocation } from "../router";
import { useDocumentTitle } from "./ui";
import {
  CONTACT_REASONS,
  contactReasonLabel,
  isContactReason,
  type ContactReasonKey,
} from "../data/contactReasons";
import { CONTACT_EMAIL } from "../data/site";

const inputClass =
  "w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

/** Build the mailto: URL the form opens. Exported for tests. */
export function buildMailto(fields: {
  name: string;
  email: string;
  organization: string;
  reason: ContactReasonKey;
  message: string;
}) {
  const label = contactReasonLabel(fields.reason);
  const subject = encodeURIComponent(`[${label}] Contact from ${fields.name}`);
  const header = [
    `Name: ${fields.name}`,
    `Email: ${fields.email}`,
    fields.organization && `Organization: ${fields.organization}`,
    `Reason: ${label}`,
  ]
    .filter(Boolean)
    .join("\n");
  const body = encodeURIComponent(`${header}\n\n${fields.message}`);
  return `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
}

export default function ContactPage() {
  useDocumentTitle("Contact Us");
  const { search } = useLocation();
  const requested = new URLSearchParams(search).get("reason");
  const initialReason: ContactReasonKey = isContactReason(requested)
    ? requested
    : "general";

  const [submitted, setSubmitted] = useState(false);
  const loadTimeRef = useRef(Date.now());
  const honeypotRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Bot detection: honeypot field should be empty
    if (honeypotRef.current?.value) return;

    // Bot detection: form submitted too fast (< 3 seconds)
    if (Date.now() - loadTimeRef.current < 3000) return;

    const data = new FormData(e.currentTarget);
    const reason = String(data.get("reason") ?? "general");
    window.location.href = buildMailto({
      name: String(data.get("name") ?? ""),
      email: String(data.get("email") ?? ""),
      organization: String(data.get("organization") ?? ""),
      reason: isContactReason(reason) ? reason : "general",
      message: String(data.get("message") ?? ""),
    });
    setSubmitted(true);
  };

  return (
    <section className="px-4 py-16 sm:py-24">
      <div className="mx-auto max-w-xl">
        <Link
          href="/"
          className="mb-8 inline-flex items-center text-sm font-medium text-primary hover:underline"
        >
          &larr; Back to Home
        </Link>

        <h1 className="mb-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Contact Us
        </h1>
        <p className="mb-8 text-muted-foreground">
          Have a question or want to get in touch? Fill out the form below and
          your email app will open with the message ready to send.
        </p>

        {submitted ? (
          <div className="rounded-lg border border-border bg-accent/50 p-6 text-center">
            <p className="text-lg font-medium text-foreground">
              Thanks for reaching out!
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Your email client should have opened with the message. If it
              didn't, you can email us directly at{" "}
              <a
                href={`mailto:${CONTACT_EMAIL}`}
                className="text-foreground underline underline-offset-4"
              >
                {CONTACT_EMAIL}
              </a>
              .
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Honeypot — hidden from real users, bots will fill it */}
            <div className="absolute left-[-9999px]" aria-hidden="true">
              <label htmlFor="website">Website</label>
              <input
                ref={honeypotRef}
                type="text"
                id="website"
                name="website"
                tabIndex={-1}
                autoComplete="off"
              />
            </div>

            <div>
              <label
                htmlFor="reason"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                What's this about?
              </label>
              <select
                id="reason"
                name="reason"
                // Re-mount when the URL's ?reason= changes, so a second
                // in-site link to /contact preselects its own reason.
                key={initialReason}
                defaultValue={initialReason}
                className={inputClass}
              >
                {CONTACT_REASONS.map((r) => (
                  <option key={r.key} value={r.key}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="name"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                required
                className={inputClass}
                placeholder="Your name"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                Email
              </label>
              <input
                type="email"
                id="email"
                name="email"
                required
                className={inputClass}
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="organization"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                Organization{" "}
                <span className="font-normal text-muted-foreground">
                  (optional)
                </span>
              </label>
              <input
                type="text"
                id="organization"
                name="organization"
                className={inputClass}
                placeholder="Agency, university or company"
              />
            </div>

            <div>
              <label
                htmlFor="message"
                className="mb-1 block text-sm font-medium text-foreground"
              >
                Message
              </label>
              <textarea
                id="message"
                name="message"
                required
                rows={5}
                className={inputClass}
                placeholder="How can we help?"
              />
            </div>

            <button
              type="submit"
              className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              Send Message
            </button>
          </form>
        )}
      </div>
    </section>
  );
}
