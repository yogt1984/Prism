/** TypeScript types matching FastAPI response schemas. */

export type BiasLabel =
  | "left"
  | "center_left"
  | "center"
  | "center_right"
  | "right"
  | "unknown";

export type BriefingFormat = "email" | "json_feed" | "audio_script";

export type Category =
  | "finance"
  | "politics"
  | "technology"
  | "sports"
  | "culture"
  | "science"
  | "health"
  | "world";

export const CATEGORIES: Category[] = [
  "finance",
  "politics",
  "technology",
  "sports",
  "culture",
  "science",
  "health",
  "world",
];

export interface Source {
  id: number;
  name: string;
  url: string;
  rss_url: string;
  trust_score: number;
  bias_label: BiasLabel;
  categories: string;
  active: boolean;
  created_at: string;
}

export interface Story {
  id: number;
  headline: string;
  summary: string;
  categories: string;
  status: "raw" | "analyzed";
  article_count: number;
  prompt_version: string;
  quality_score: number;
  resonance_score: number;
  first_seen: string;
  last_updated: string;
}

export interface Article {
  id: number;
  source_id: number;
  title: string;
  url: string;
  snippet: string;
  published_at: string | null;
  fetched_at: string;
}

export interface Perspective {
  id: number;
  source_id: number;
  summary: string;
  sentiment: number;
  bias_label: BiasLabel;
  key_claims: string;
}

export interface StoryDetail extends Story {
  articles: Article[];
  perspectives: Perspective[];
}

export interface Resonance {
  cluster_id: number;
  resonance: number;
  momentum: number;
  peak_resonance: number;
  mention_count: number;
  source_count: number;
  authority_weighted_sum: number;
  breadth: number;
  window_hours: number;
  computed_at: string;
}

export interface User {
  id: number;
  email: string;
  name: string;
  interests: string;
  preferred_format: BriefingFormat;
  briefing_depth: number;
  is_pro: boolean;
  created_at: string;
}

export interface Briefing {
  id: number;
  user_id: number;
  story_count: number;
  prompt_version: string;
  sent: boolean;
  sent_at: string | null;
  created_at: string;
}

export interface BriefingDetail extends Briefing {
  content_html: string;
  content_text: string;
}

export interface Engagement {
  id: number;
  user_id: number;
  cluster_id: number;
  action: "open" | "read" | "save" | "skip";
  read_time_sec: number;
  created_at: string;
}

export interface Keyword {
  id: number;
  keyword: string;
  aliases: string;
  category: string;
  is_active: boolean;
  created_at: string;
}

export interface PerceptionSnapshot {
  keyword_id: number;
  perception: number;
  salience: number;
  valence: number;
  momentum: number;
  cluster_count: number;
  source_count: number;
  computed_at: string;
}
