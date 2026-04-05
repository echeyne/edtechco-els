import { useState, useRef, FormEvent } from "react";

export default function ContactPage({ onBack }: { onBack: () => void }) {
  const [submitted, setSubmitted] = useState(false);
  const loadTimeRef = useRef(Date.now());
  const honeypotRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    // Bot detection: honeypot field should be empty
    if (honeypotRef.current?.value) return;

    // Bot detection: form submitted too fast (< 3 seconds)
    if (Date.now() - loadTimeRef.current < 3000) return;

    const form = e.currentTarget;
    const data = new FormData(form);
    const name = data.get("name") as string;
    const email = data.get("email") as string;
    const message = data.get("message") as string;

    const subject = encodeURIComponent(`Contact from ${name}`);
    const body = encodeURIComponent(
      `Name: ${name}\nEmail: ${email}\n\n${message}`,
    );

    window.location.href = `mailto:info@edtechco.org?subject=${subject}&body=${body}`;
    setSubmitted(true);
  };

  return (
    <section className="px-4 py-16 sm:py-24">
      <div className="mx-auto max-w-xl">
        <button
          onClick={onBack}
          className="mb-8 inline-flex items-center text-sm font-medium text-primary hover:underline"
        >
          &larr; Back to Home
        </button>

        <h1 className="mb-4 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
          Contact Us
        </h1>
        <p className="mb-8 text-muted-foreground">
          Have a question or want to get in touch? Fill out the form below and
          we'll hear from you via email.
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
                href="mailto:info@edtechco.org"
                className="text-foreground underline underline-offset-4"
              >
                info@edtechco.org
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
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
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
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="you@example.com"
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
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
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
