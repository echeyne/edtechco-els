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
    </section>
  );
}
