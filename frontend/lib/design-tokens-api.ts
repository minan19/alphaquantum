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

/** Browser localStorage'tan token oku. Auth-context'in yazdığı key ile EŞLEŞMELİ. */
function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  // lib/api.ts'teki TOKEN_KEY ile birebir aynı olmalı (auth-context login bunu yazıyor).
  return window.localStorage.getItem("aq.access_token");
}

// ---------------------------------------------------------------------------
// Faz 5 — Snapshot/Restore client API
// ---------------------------------------------------------------------------

export type SnapshotSource = "pre_save" | "pre_restore" | "pre_reset" | "manual";

export interface SnapshotSummary {
  id: number;
  scope: Scope;
  source: SnapshotSource;
  label: string;
  created_by: string | null;
  taken_at: number;
}

export interface SnapshotListResponse {
  scope: Scope;
  snapshots: SnapshotSummary[];
}

export interface SnapshotCreateResponse {
  snapshot_id: number;
  scope: Scope;
  label: string;
  taken_at: number;
}

export interface RestoreResponse {
  scope: Scope;
  snapshot_id: number;
  pre_restore_snapshot_id: number;
  restored_count: number;
}

async function authedFetch<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${getStoredToken() ?? ""}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({ detail: res.statusText }))) as {
      detail?: string;
    };
    throw new Error(body.detail ?? `${init.method ?? "GET"} ${url} failed (${res.status})`);
  }
  return (await res.json()) as T;
}

export function listSnapshots(scope: Scope, limit = 20): Promise<SnapshotListResponse> {
  return authedFetch(
    `/api/admin/design-tokens/snapshots?scope=${encodeURIComponent(scope)}&limit=${limit}`,
  );
}

export function createManualSnapshot(
  scope: Scope,
  label: string,
): Promise<SnapshotCreateResponse> {
  return authedFetch("/api/admin/design-tokens/snapshot", {
    method: "POST",
    body: JSON.stringify({ scope, label }),
  });
}

export function restoreSnapshot(snapshotId: number): Promise<RestoreResponse> {
  return authedFetch("/api/admin/design-tokens/restore", {
    method: "POST",
    body: JSON.stringify({ snapshot_id: snapshotId }),
  });
}

export type { Token };
