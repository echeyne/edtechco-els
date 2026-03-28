import type { Article } from "../data/articles";

export interface ArticleLinkProps {
  article: Article;
}

export default function ArticleLink({ article }: ArticleLinkProps) {
  return (
    <div className="rounded-lg border border-border bg-background p-6 shadow-sm transition-shadow hover:shadow-md">
      <h3 className="text-lg font-semibold text-foreground">{article.title}</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        {article.description}
      </p>
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary transition-colors hover:text-primary/80"
      >
        Read Article
        <span aria-hidden="true">↗</span>
      </a>
    </div>
  );
}
