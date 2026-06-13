/**
 * Faz 6 — POST /api/admin/fonts (Google) + GET liste proxy.
 *
 * GET → backend /api/v1/fonts (public, scope opsiyonel).
 * POST → google source ekleme. Upload ayrı route'da (multipart).
 * Yazma sonrası revalidateTag('design-tokens') — FontLoader cache invalidate.
 */

import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const scope = url.searchParams.get("scope");
  const upstreamUrl = scope
    ? `${BACKEND_URL}/api/v1/fonts?scope=${encodeURIComponent(scope)}`
    : `${BACKEND_URL}/api/v1/fonts`;
  const upstream = await fetch(upstreamUrl, { cache: "no-store" });
  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));
  return NextResponse.json(payload, { status: upstream.status });
}

export async function POST(req: Request) {
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ detail: "Missing Authorization header" }, { status: 401 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON body" }, { status: 400 });
  }

  const upstream = await fetch(`${BACKEND_URL}/api/v1/fonts/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: auth },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));
  if (upstream.ok) {
    revalidateTag("design-tokens");
  }
  return NextResponse.json(payload, { status: upstream.status });
}
