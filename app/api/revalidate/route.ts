import { timingSafeEqual } from "node:crypto";
import { revalidateTag } from "next/cache";

import { BLOG_TAG } from "@/lib/blog";

/**
 * Called by a Sanity webhook (sanity.io/manage → API → Webhooks) when a post
 * is created, updated or deleted. Sanity sends
 * `Authorization: Bearer <SANITY_REVALIDATE_SECRET>` as a custom header.
 */
export async function POST(request: Request) {
  const secret = process.env.SANITY_REVALIDATE_SECRET;
  if (!secret) {
    return Response.json({ message: "SANITY_REVALIDATE_SECRET is not set" }, { status: 500 });
  }

  const given = Buffer.from(request.headers.get("authorization") ?? "");
  const expected = Buffer.from(`Bearer ${secret}`);
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) {
    return Response.json({ message: "Invalid secret" }, { status: 401 });
  }

  // expire: 0 so the next visitor gets the new content, not one last stale copy.
  revalidateTag(BLOG_TAG, { expire: 0 });
  return Response.json({ revalidated: true, now: Date.now() });
}
