import { NextResponse, type NextRequest } from "next/server";

/**
 * A convenience redirect, NOT a security check. The csrf_token cookie is the only session cookie
 * the browser sends to page routes (the refresh cookie is scoped to /api/v1/auth, and the access
 * cookie expires after 15 minutes while the session can outlive it). Without it there is
 * certainly no session, so the visitor goes to sign in without waiting for the page to load.
 * With it, the page's own session check against the backend decides, and the backend rejects
 * every unauthenticated API call regardless.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has("csrf_token")) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  const target = `${request.nextUrl.pathname}${request.nextUrl.search}`;
  if (target !== "/") url.searchParams.set("next", target);
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except the public pages, the API proxy, Next.js internals and static files.
  matcher: ["/((?!api|_next|login|register|diagnostics|favicon\\.ico|.*\\..*).*)"],
};
