import type {
  Article,
  Engagement,
  Perspective,
  Resonance,
  Source,
  Story,
  StoryDetail,
  Briefing,
  BriefingDetail,
  Keyword,
  PerceptionSnapshot,
} from "@/lib/types";

export function makeStory(overrides: Partial<Story> = {}): Story {
  return {
    id: 1,
    headline: "Fed Holds Rates Steady Despite Market Pressure",
    summary: "The Federal Reserve decided to maintain current interest rates.",
    categories: "finance,politics",
    status: "analyzed",
    article_count: 8,
    prompt_version: "v2",
    quality_score: 0.85,
    resonance_score: 4.72,
    first_seen: new Date(Date.now() - 3_600_000).toISOString(),
    last_updated: new Date(Date.now() - 1_800_000).toISOString(),
    ...overrides,
  };
}

export function makeBriefing(overrides: Partial<Briefing> = {}): Briefing {
  return {
    id: 42,
    user_id: 5,
    story_count: 10,
    prompt_version: "v2",
    sent: true,
    sent_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makeBriefingDetail(
  overrides: Partial<BriefingDetail> = {},
): BriefingDetail {
  return {
    ...makeBriefing(),
    content_html:
      "<h2>Morning Briefing</h2><p>The Fed held rates steady in a move that surprised few analysts but rattled markets briefly.</p>",
    content_text:
      "Morning Briefing\nThe Fed held rates steady in a move that surprised few analysts but rattled markets briefly.",
    ...overrides,
  };
}

export function makeKeyword(overrides: Partial<Keyword> = {}): Keyword {
  return {
    id: 7,
    keyword: "tariffs",
    aliases: "trade war,import duties",
    category: "finance",
    is_active: true,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makePerception(
  overrides: Partial<PerceptionSnapshot> = {},
): PerceptionSnapshot {
  return {
    keyword_id: 7,
    perception: -0.35,
    salience: 2.1,
    valence: -0.17,
    momentum: -0.05,
    cluster_count: 4,
    source_count: 12,
    computed_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makePerceptionHistory(
  count: number = 20,
  keywordId: number = 7,
): PerceptionSnapshot[] {
  return Array.from({ length: count }, (_, i) => ({
    keyword_id: keywordId,
    perception: Math.sin(i * 0.3) * 0.5,
    salience: 1.5 + Math.random(),
    valence: Math.cos(i * 0.3) * 0.3,
    momentum: i === count - 1 ? 0.15 : 0,
    cluster_count: 3 + Math.floor(Math.random() * 5),
    source_count: 8 + Math.floor(Math.random() * 10),
    computed_at: new Date(
      Date.now() - (count - i) * 3_600_000,
    ).toISOString(),
  }));
}

export function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: 1,
    name: "Reuters",
    url: "https://reuters.com",
    rss_url: "https://reuters.com/rss",
    trust_score: 0.95,
    bias_label: "center",
    categories: "finance,politics,world",
    active: true,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makeArticle(overrides: Partial<Article> = {}): Article {
  return {
    id: 1,
    source_id: 1,
    title: "Fed Holds Rates Steady",
    url: "https://reuters.com/article/fed-rates",
    snippet: "The Federal Reserve decided to maintain current interest rates.",
    published_at: new Date(Date.now() - 3_600_000).toISOString(),
    fetched_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makePerspective(
  overrides: Partial<Perspective> = {},
): Perspective {
  return {
    id: 1,
    source_id: 1,
    summary: "Reuters reports the Fed held rates steady in a widely expected move.",
    sentiment: 0.1,
    bias_label: "center",
    key_claims: JSON.stringify([
      "Fed maintains current rate range",
      "Decision was unanimous",
    ]),
    ...overrides,
  };
}

export function makeResonance(
  overrides: Partial<Resonance> = {},
): Resonance {
  return {
    cluster_id: 1,
    resonance: 4.72,
    momentum: 0.15,
    peak_resonance: 5.1,
    mention_count: 42,
    source_count: 8,
    authority_weighted_sum: 12.5,
    breadth: 0.78,
    window_hours: 24,
    computed_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makeStoryDetail(
  overrides: Partial<StoryDetail> = {},
): StoryDetail {
  return {
    ...makeStory(),
    articles: [
      makeArticle({ id: 1, source_id: 1, title: "Reuters: Fed Holds Rates" }),
      makeArticle({
        id: 2,
        source_id: 2,
        title: "AP: Federal Reserve Keeps Rates Unchanged",
        url: "https://apnews.com/fed-rates",
      }),
    ],
    perspectives: [
      makePerspective({ id: 1, source_id: 1, bias_label: "center" }),
      makePerspective({
        id: 2,
        source_id: 2,
        summary: "AP reports the Fed decision reflects cautious optimism.",
        sentiment: 0.3,
        bias_label: "center_left",
      }),
    ],
    ...overrides,
  };
}

export function makeEngagement(
  overrides: Partial<Engagement> = {},
): Engagement {
  return {
    id: 1,
    user_id: 5,
    cluster_id: 1,
    action: "open",
    read_time_sec: 0,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makeSources(count: number = 3): Source[] {
  const names = ["Reuters", "AP News", "BBC", "CNN", "Fox News"];
  const biases: Source["bias_label"][] = [
    "center",
    "center_left",
    "center",
    "center_left",
    "right",
  ];
  return Array.from({ length: count }, (_, i) =>
    makeSource({
      id: i + 1,
      name: names[i % names.length],
      bias_label: biases[i % biases.length],
    }),
  );
}

export function makeTopStories(count: number = 5): Story[] {
  const categories = [
    "finance",
    "politics",
    "technology",
    "sports",
    "science",
  ];
  return Array.from({ length: count }, (_, i) =>
    makeStory({
      id: i + 1,
      headline: `Top Story ${i + 1}: Something Important Happened`,
      categories: categories[i % categories.length],
      resonance_score: 5 - i * 0.8,
      article_count: 10 - i,
      first_seen: new Date(Date.now() - i * 3_600_000).toISOString(),
    }),
  );
}

export function makeRecentStories(
  count: number = 20,
  offset: number = 0,
): Story[] {
  return Array.from({ length: count }, (_, i) =>
    makeStory({
      id: offset + i + 100,
      headline: `Recent Story ${offset + i + 1}`,
      resonance_score: 2 - i * 0.05,
      first_seen: new Date(
        Date.now() - (offset + i) * 1_800_000,
      ).toISOString(),
    }),
  );
}
