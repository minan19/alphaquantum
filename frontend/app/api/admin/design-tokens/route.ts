/**
 * Faz 4 — PATCH /api/admin/design-tokens route handler.
 *
 * Backend `/api/v1/design-tokens`'a PATCH proxy ile gider.
 * Başarılıysa `revalidateTag('design-tokens')` tetiklenir → Faz 2 SSR cascade
 * bir sonraki istekte yeni değerleri okur (cascade-probe sayfaları canlı yansır).
 */

import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function PATCH(req: Request) {
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

  const upstream = await fetch(`${BACKEND_URL}/api/v1/design-tokens`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: auth,
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));

  if (upstream.ok) {
    // Cascade-probe ve gerçek sayfalar bir sonraki SSR'da yeni token değerlerini okur.
    revalidateTag("design-tokens");
  }

  return NextResponse.json(payload, { status: upstream.status });
}
