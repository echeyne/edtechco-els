export default function Hero() {
  return (
    <section
      id="hero"
      className="flex min-h-[40vh] flex-col items-center justify-center py-24 pb-4 text-center"
    >
      <h1 className="text-5xl font-bold tracking-tight text-foreground sm:text-6xl lg:text-7xl">
        EdTech Co.
      </h1>

      <p className="mt-6 max-w-2xl text-lg text-muted-foreground sm:text-xl">
        Innovating ways to make the use of data easier in education.
      </p>

      <a
        href="#projects"
        className="mt-10 inline-flex items-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        View Our Projects
      </a>
    </section>
  );
}
