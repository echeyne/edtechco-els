import { articles as defaultArticles, type Article } from "../data/articles";
import ArticleLink from "./ArticleLink";

interface ArticlesSectionProps {
  articles?: Article[];
}

export default function ArticlesSection({
  articles = defaultArticles,
}: ArticlesSectionProps) {
  return (
    <section id="articles" className="px-4 pb-16">
      <h2 className="mb-10 text-center text-3xl font-bold tracking-tight text-foreground sm:text-4xl">
        Articles
      </h2>
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {articles.map((article) => (
          <ArticleLink key={article.title} article={article} />
        ))}
      </div>
    </section>
  );
}
