import { ButtonLink } from "./ui";

export const AUDIENCES = [
  { label: "For state agencies", href: "/for-states" },
  { label: "For researchers", href: "/for-researchers" },
  { label: "For curriculum teams", href: "/for-curriculum" },
];

export default function Hero() {
  return (
    <section
      id="hero"
      className="flex min-h-[40vh] flex-col items-center justify-center px-4 py-24 pb-16 text-center"
    >
      <p className="mb-4 text-sm font-semibold uppercase tracking-wide text-primary">
        EdTech Co.
      </p>
      <h1 className="max-w-4xl text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
        Every state's early learning standards, as structured data
      </h1>

      <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
        Each state publishes its standards as a differently designed PDF. We
        turn them into one consistent, checkable dataset that software,
        researchers and agencies can use.
      </p>

      <div className="mt-10 flex flex-wrap justify-center gap-3">
        {AUDIENCES.map((a, i) => (
          <ButtonLink
            key={a.href}
            href={a.href}
            variant={i === 0 ? "primary" : "secondary"}
          >
            {a.label}
          </ButtonLink>
        ))}
      </div>
    </section>
  );
}
