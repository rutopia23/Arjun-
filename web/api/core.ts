import type { IncomingMessage, ServerResponse } from "node:http";
import { access, coreUrl } from "./_gate.js";

/** /core/* -> core-api. The access check and header rules are exactly server/access.ts (key only after a valid link
 * cookie; account routes carry only core-api's own session cookie, never the key). No WebSocket here: Vercel
 * functions cannot hold one, so the family feed uses its REST fallback (web/src/family/feed.ts). */
async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(Buffer.from(c as Uint8Array));
  return Buffer.concat(chunks);
}

export default async function handler(req: IncomingMessage, res: ServerResponse): Promise<void> {
  const incoming = new URL(req.url ?? "/", "https://local");
  const p = incoming.searchParams.get("p") ?? "";
  incoming.searchParams.delete("p");
  const qs = incoming.searchParams.toString();
  req.url = `/core/${p}${qs ? `?${qs}` : ""}`; // the shape server/access.ts expects
  const verdict = access.decideCore(req);
  if (!verdict.ok) {
    res.statusCode = verdict.status;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ detail: verdict.detail }));
    return;
  }
  if (!coreUrl) {
    res.statusCode = 503;
    res.end(JSON.stringify({ detail: "CORE_API_URL is not set" }));
    return;
  }
  const headers = new Map<string, string>();
  for (const [k, v] of Object.entries(req.headers)) {
    if (typeof v === "string" && ["content-type", "accept", "accept-language", "cookie"].includes(k)) headers.set(k, v);
  }
  access.onProxyReq({ setHeader: (n, v) => void headers.set(n.toLowerCase(), v), removeHeader: (n) => void headers.delete(n.toLowerCase()) }, req);
  const method = (req.method ?? "GET").toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await readBody(req);
  const upstream = await fetch(`${coreUrl}/${p}${qs ? `?${qs}` : ""}`, {
    method,
    headers: Object.fromEntries(headers),
    body: body && body.length ? new Uint8Array(body) : undefined,
    redirect: "manual",
  });
  res.statusCode = upstream.status;
  upstream.headers.forEach((v, k) => {
    if (!["content-encoding", "content-length", "transfer-encoding", "connection", "set-cookie"].includes(k)) res.setHeader(k, v);
  });
  const cookies = upstream.headers.getSetCookie();
  if (cookies.length) res.setHeader("Set-Cookie", cookies);
  res.end(Buffer.from(await upstream.arrayBuffer()));
}
