import { Link } from "../router";
import { contactHref } from "./ui";

/** Short "who's behind this" note; the full profile lives on /about. */
export default function AboutSection() {
  return (
    <section id="about" className="px-4 pb-20">
      <div className="mx-auto max-w-3xl rounded-lg border border-border bg-secondary px-6 py-8 text-center">
        <h2 className="text-2xl font-bold tracking-tight text-foreground">
          Who's behind this
        </h2>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          EdTech Co. is the independent research practice of Emily Cheyne, a
          software engineer who builds and maintains this dataset and the
          pipeline behind it.
        </p>
        <p className="mt-4 flex flex-wrap justify-center gap-x-6 gap-y-2 text-sm font-medium">
          <Link
            href="/about"
            className="text-primary transition-colors hover:text-primary/80"
          >
            About Emily →
          </Link>
          <Link
            href={contactHref("general")}
            className="text-primary transition-colors hover:text-primary/80"
          >
            Get in touch →
          </Link>
        </p>
      </div>
    </section>
  );
}
