/**
 * Design Token Programı — Faz 2 · middleware
 *
 * Yalnız tek iş: gelen request'in pathname'ini `x-pathname` header'ı olarak
 * propagate eder. Root layout `await headers()` ile bu header'ı okuyup
 * `<html data-module>` değerini belirler.
 *
 * Neden middleware? Next.js 15 App Router'da `headers()` request meta'yı
 * doğrudan vermez; pathname'i layout'a taşımak için tek temiz yol budur.
 * FLASH YOK: data-module SSR'da set edilir, JS hidratasyonu beklenmez.
 */
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export function middleware(request: NextRequest): NextResponse {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-pathname", request.nextUrl.pathname);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = {
  /**
   * Statik asset'leri ve API'leri es geç — yalnız sayfa request'leri.
   */
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
