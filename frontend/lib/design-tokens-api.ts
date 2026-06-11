/**
 * Faz 4 — Design Tokens admin API client.
 *
 * `getTokens()` Faz 2'de unstable_cache'li server-side fetch yapıyor;
 * bu modül CLIENT-side panel mutations için ayrı bir API client sağlar.
 * Mutations frontend route handler üzerinden geçer (revalidateTag tetikleme için).
 */

import { apiRequest } from "@/lib/api";
import type { Scope, Token, TokenCategory } from "@/lib/tokens";

export interface DesignTokensListResponse {
  tokens: Array<{
    scope: Scope;
    key: string;
    value: string;
    label: string;
    category: TokenCategory;
    order: number;
    updated_at: number;
  }>;
  scope_filter: Scope | null;
  seeded_at: number | null;
}

export interface PatchResponse {
  scope: Scope;
  updated: string[];
  updated_count: number;
}

export interface ResetResponse {
  scope: Scope;
  deleted: number;
  inserted: number;
}

/** Client-side: tüm scope'ları çek (panel açılışında). */
export function fetchAllTokensClient(): Promise<DesignTokensListResponse> {
  return apiRequest<DesignTokensListResponse>("/api/v1/design-tokens");
}

/** Panel "Kaydet": Next route handler proxy üzerinden PATCH + revalidateTag. */
export async function patchTokens(
  scope: Scope,
  changes: Record<string, string | number>,
): Promise<PatchResponse> {
  const res = await fetch("/api/admin/design-tokens", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getStoredToken() ?? ""}`,
    },
    body: JSON.stringify({ scope, changes }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({ detail: res.statusText }))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? `PATCH failed (${res.status})`);
  }
  return (await res.json()) as PatchResponse;
}

/** Panel "Fabrika": Next route handler proxy üzerinden reset + revalidateTag. */
export async function resetScope(scope: Scope): Promise<ResetResponse> {
  const res = await fetch("/api/admin/design-tokens/reset", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getStoredToken() ?? ""}`,
    },
    body: JSON.stringify({ scope }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({ detail: res.statusText }))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? `Reset failed (${res.status})`);
  }
  return (await res.json()) as ResetResponse;
}

/** Browser localStorage'tan token oku. */
function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("aq_access_token");
}

export type { Token };
