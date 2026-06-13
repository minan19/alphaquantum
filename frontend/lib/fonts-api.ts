/**
 * Faz 6 — CustomFonts admin API client (browser).
 */

import type { Scope } from "@/lib/tokens";
import type { CustomFont, CustomFontListResponse } from "@/lib/fonts";
import { buildGoogleFontUrl } from "@/lib/fonts";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("aq.access_token");
}

async function authedJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${getStoredToken() ?? ""}`);
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
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

export function listFontsClient(scope?: Scope): Promise<CustomFontListResponse> {
  const qs = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  return authedJson(`/api/admin/fonts${qs}`);
}

export function addGoogleFont(args: {
  scope: Scope;
  family: string;
  weights?: number[];
  make_default?: boolean;
}): Promise<CustomFont> {
  return authedJson("/api/admin/fonts", {
    method: "POST",
    body: JSON.stringify({
      scope: args.scope,
      family: args.family,
      css_url: buildGoogleFontUrl(args.family, args.weights ?? [400, 500, 600, 700]),
      make_default: args.make_default ?? false,
    }),
  });
}

export function uploadFont(args: {
  scope: Scope;
  family: string;
  format: string;
  file: File;
  make_default?: boolean;
}): Promise<CustomFont> {
  const fd = new FormData();
  fd.set("scope", args.scope);
  fd.set("family", args.family);
  fd.set("format", args.format);
  fd.set("file", args.file);
  if (args.make_default) fd.set("make_default", "true");
  return authedJson("/api/admin/fonts/upload", {
    method: "POST",
    body: fd,
  });
}

export function setDefaultFont(id: number) {
  return authedJson(`/api/admin/fonts/${id}/default`, { method: "POST" });
}

export function deleteFont(id: number) {
  return authedJson(`/api/admin/fonts/${id}`, { method: "DELETE" });
}
