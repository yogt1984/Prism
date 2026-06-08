import TimeAgo from "@/components/dashboard/TimeAgo";
import type { Article, Source } from "@/lib/types";

interface ArticleSourcesListProps {
  articles: Article[];
  sourceMap: Map<number, Source>;
}

export default function ArticleSourcesList({
  articles,
  sourceMap,
}: ArticleSourcesListProps) {
  if (articles.length === 0) return null;

  return (
    <section>
      <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Original Sources
      </h2>
      <div className="divide-y divide-gray-100" data-testid="article-list">
        {articles.map((article) => {
          const source = sourceMap.get(article.source_id);
          return (
            <div
              key={article.id}
              className="flex items-center gap-3 py-3"
              data-testid="article-row"
            >
              <span className="text-xs font-medium text-gray-500 w-24 truncate flex-shrink-0">
                {source?.name ?? `#${article.source_id}`}
              </span>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 text-sm font-medium text-violet-600 hover:underline truncate"
              >
                {article.title}
              </a>
              {article.published_at && (
                <span className="text-xs text-gray-400 flex-shrink-0">
                  <TimeAgo date={article.published_at} />
                </span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
