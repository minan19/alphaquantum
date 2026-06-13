/**
 * Faz 5 — POST /api/admin/design-tokens/restore route handler.
 *
 * Backend `/api/v1/design-tokens/restore` proxy. Token store değişir → SSR cache
 * invalidate edilmeli ki cascade canlı yansısın (Faz 2 unstable_cache).
 */

import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

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

  const upstream = await fetch(`${BACKEND_URL}/api/v1/design-tokens/restore`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));

  if (upstream.ok) {
    revalidateTag("design-tokens");
  }

  return NextResponse.json(payload, { status: upstream.status });
}
