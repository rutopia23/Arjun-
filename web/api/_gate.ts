/** Shared by the Vercel functions: the same access gate as the Vite dev proxy (server/access.ts), run server-side so
 * CORE_API_KEY lives only in Vercel's environment. UNVERIFIED on Vercel until the smoke test in docs/DEPLOY_CLOUD.md. */
import { createAccess } from "../server/access";

export const coreUrl = (process.env.CORE_API_URL ?? "").replace(/\/+$/, "");
export const access = createAccess({
  code: (process.env.ARJUN_ACCESS_CODE ?? "").trim(),
  apiKey: process.env.CORE_API_KEY ?? "",
  // ARJUN_AUTH=1: per-user accounts; core-api checks the session / device cookie, the key is never injected
  accounts: process.env.ARJUN_AUTH === "1",
});
