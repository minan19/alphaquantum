/**
 * Faz 4 — POST /api/admin/design-tokens/reset route handler (Fabrika).
 *
 * Backend `/api/v1/design-tokens/reset` proxy + revalidateTag.
 * İki adımlı onay UI'da; backend tek atomik op.
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

  const upstream = await fetch(`${BACKEND_URL}/api/v1/design-tokens/reset`, {
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
