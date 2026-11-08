import { Link } from "../router";
import { articles as defaultArticles, type Article } from "../data/articles";
import ArticleLink from "./ArticleLink";

interface ArticlesSectionProps {
  articles?: Article[];
}

/** The featured articles only; the full list is on /about#writing. */
export default function ArticlesSection({
  articles = defaultArticles,
}: ArticlesSectionProps) {
  const featured = articles.filter((a) => a.featured);
  if (featured.length === 0) return null;
  return (
    <section id="articles" className="px-4 pb-16">
      <h2 className="mb-10 text-center text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Writing
      </h2>
      <div className="mx-auto grid max-w-4xl grid-cols-1 gap-6 md:grid-cols-2">
        {featured.map((article) => (
          <ArticleLink key={article.title} article={article} />
        ))}
      </div>
      {articles.length > featured.length && (
        <p className="mt-6 text-center text-sm">
          <Link
            href="/about#writing"
            className="font-medium text-primary transition-colors hover:text-primary/80"
          >
            All writing →
          </Link>
        </p>
      )}
    </section>
  );
}
