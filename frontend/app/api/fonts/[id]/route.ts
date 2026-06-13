/**
 * Faz 6 — Public /api/fonts/<id> — @font-face src bu uçtan baytları çeker.
 *
 * Cache: backend zaten 'public, max-age=31536000, immutable' set ediyor;
 * Next proxy aynısını forward eder (immutable bayt akışı).
 */

import { NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.AQ_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const upstream = await fetch(`${BACKEND_URL}/api/v1/fonts/${encodeURIComponent(id)}/file`, {
    cache: "no-store",
  });
  if (!upstream.ok) {
    return NextResponse.json({ detail: "not found" }, { status: upstream.status });
  }
  const buf = await upstream.arrayBuffer();
  const headers = new Headers();
  const ct = upstream.headers.get("content-type") ?? "application/octet-stream";
  headers.set("Content-Type", ct);
  // Backend cache header'ını koru (1 yıl + immutable).
  const cc = upstream.headers.get("cache-control");
  if (cc) headers.set("Cache-Control", cc);
  return new NextResponse(buf, { status: 200, headers });
}
