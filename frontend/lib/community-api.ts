/**
 * BZ3: Public changelog + roadmap voting — API client.
 */
import { apiRequest } from "@/lib/api";

export type ChangelogCategory = "feature" | "fix" | "improvement" | "security";
export type RoadmapCategory =
  | "feature" | "integration" | "analytics" | "ux" | "security" | "mobile";
export type RoadmapStatus =
  | "idea" | "planned" | "in_progress" | "shipped" | "declined";

export interface ChangelogEntry {
  id: number;
  version: string;
  title: string;
  description: string;
  category: ChangelogCategory;
  released_at: number;
  created_at: number;
  created_by: string | null;
}

export interface ChangelogList {
  entries: ChangelogEntry[];
  total: number;
}

export interface RoadmapItem {
  id: number;
  title: string;
  description: string;
  category: RoadmapCategory;
  status: RoadmapStatus;
  upvotes: number;
  submitter: string | null;
  target_quarter: string | null;
  shipped_changelog_id: number | null;
  created_at: number;
  updated_at: number;
  has_voted: boolean;
}

export interface RoadmapList {
  items: RoadmapItem[];
  total: number;
}

export interface VoteResponse {
  item_id: number;
  voted: boolean;
  upvotes_after: number;
}

export interface CommunityStats {
  shipped_features: number;
  in_progress: number;
  planned: number;
  open_ideas: number;
  total_votes: number;
}


export async function fetchChangelog(
  params?: { limit?: number; category?: ChangelogCategory },
): Promise<ChangelogList> {
  const search = new URLSearchParams();
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.category) search.set("category", params.category);
  const qs = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<ChangelogList>(`/api/v1/changelog${qs}`);
}

export async function fetchRoadmap(
  params?: { status?: RoadmapStatus; category?: RoadmapCategory; limit?: number },
): Promise<RoadmapList> {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.category) search.set("category", params.category);
  if (params?.limit) search.set("limit", String(params.limit));
  const qs = search.toString() ? `?${search.toString()}` : "";
  return apiRequest<RoadmapList>(`/api/v1/roadmap${qs}`);
}

export async function submitRoadmapIdea(payload: {
  title: string;
  description: string;
  category: RoadmapCategory;
}): Promise<RoadmapItem> {
  return apiRequest<RoadmapItem>("/api/v1/roadmap", {
    method: "POST",
    body: payload,
  });
}

export async function voteOnRoadmap(itemId: number): Promise<VoteResponse> {
  return apiRequest<VoteResponse>(`/api/v1/roadmap/${itemId}/vote`, {
    method: "POST",
  });
}

export async function fetchCommunityStats(): Promise<CommunityStats> {
  return apiRequest<CommunityStats>("/api/v1/community/stats");
}

// ── Display helpers ────────────────────────────────────────────────────

export const ROADMAP_STATUS_LABEL: Record<RoadmapStatus, string> = {
  idea: "Fikir",
  planned: "Planlandı",
  in_progress: "Üretimde",
  shipped: "Yayınlandı",
  declined: "Reddedildi",
};

export const ROADMAP_STATUS_TONE: Record<
  RoadmapStatus, "neutral" | "info" | "warn" | "success" | "critical"
> = {
  idea: "neutral",
  planned: "info",
  in_progress: "warn",
  shipped: "success",
  declined: "critical",
};

export const ROADMAP_CATEGORY_LABEL: Record<RoadmapCategory, string> = {
  feature: "Özellik",
  integration: "Entegrasyon",
  analytics: "Analitik",
  ux: "Deneyim",
  security: "Güvenlik",
  mobile: "Mobil",
};

export const CHANGELOG_CATEGORY_LABEL: Record<ChangelogCategory, string> = {
  feature: "Yeni Özellik",
  fix: "Düzeltme",
  improvement: "İyileştirme",
  security: "Güvenlik",
};

export const CHANGELOG_CATEGORY_TONE: Record<
  ChangelogCategory, "primary" | "warn" | "success" | "critical"
> = {
  feature: "primary",
  fix: "warn",
  improvement: "success",
  security: "critical",
};
