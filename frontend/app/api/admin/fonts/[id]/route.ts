/**
 * Faz 6 — DELETE /api/admin/fonts/<id>.
 */

import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const auth = req.headers.get("authorization");
  if (!auth) {
    return NextResponse.json({ detail: "Missing Authorization header" }, { status: 401 });
  }
  const { id } = await params;
  const upstream = await fetch(`${BACKEND_URL}/api/v1/fonts/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { Authorization: auth },
    cache: "no-store",
  });
  const payload = await upstream.json().catch(() => ({ detail: upstream.statusText }));
  if (upstream.ok) {
    revalidateTag("design-tokens");
  }
  return NextResponse.json(payload, { status: upstream.status });
}
