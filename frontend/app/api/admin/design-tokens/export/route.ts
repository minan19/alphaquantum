/**
 * Faz 5 — GET /api/admin/design-tokens/export route handler.
 *
 * Backend `/api/v1/design-tokens/export` proxy. Yalnız okur, store değiştirmez
 * → revalidateTag GEREKMEZ.
 */

import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(req: Request) {
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ detail: "Missing Authorization header" }, { status: 401 });
  }

  const url = new URL(req.url);
  const scope = url.searchParams.get("scope") ?? "";

  const upstream = await fetch(
    `${BACKEND_URL}/api/v1/design-tokens/export?scope=${encodeURIComponent(scope)}`,
    {
      method: "GET",
      headers: { Authorization: auth },
      cache: "no-store",
    },
  );

  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));
  return NextResponse.json(payload, { status: upstream.status });
}
