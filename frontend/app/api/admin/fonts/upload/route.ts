/**
 * Faz 6 — POST /api/admin/fonts/upload (multipart .woff2/.woff/.ttf/.otf).
 *
 * Next route handler multipart formdata'yı backend'e olduğu gibi forward eder.
 * Backend magic-byte + boyut + format kontrolü yapar (sıkı whitelist).
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

  const inForm = await req.formData();
  // Backend'e olduğu gibi proxy — multipart boundary'yi fetch otomatik üretir.
  const upstream = await fetch(`${BACKEND_URL}/api/v1/fonts/upload`, {
    method: "POST",
    headers: { Authorization: auth },
    body: inForm,
    cache: "no-store",
  });

  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));
  if (upstream.ok) {
    revalidateTag("design-tokens");
  }
  return NextResponse.json(payload, { status: upstream.status });
}
