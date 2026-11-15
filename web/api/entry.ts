import type { IncomingMessage, ServerResponse } from "node:http";
import { access } from "./_gate";

/** /auth?k=... and /?...&k=... (the phone links): check the code, set the access cookie, redirect without `k`.
 * vercel.json tags the two rewrites with m=auth / m=phone; the dev middleware (server/access.ts) does the rest. */
export default function handler(req: IncomingMessage, res: ServerResponse): void {
  const u = new URL(req.url ?? "/", "https://local");
  const mode = u.searchParams.get("m");
  u.searchParams.delete("m");
  req.url = `${mode === "auth" ? "/auth" : "/"}?${u.searchParams.toString()}`;
  access.middleware(req, res, () => {
    res.statusCode = 404;
    res.end();
  });
}
