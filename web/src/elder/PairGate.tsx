import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api";

/** Elder phone: `/?pair=<8 digits>` connects this phone to ONE elder (core-api sets the device cookie), then the
 * code is removed from the address bar. No account, no password for her. */
export function PairGate(p: { onUser: (id: number) => void; children: ReactNode }) {
  const [state, setState] = useState<"idle" | "pairing" | "failed">("idle");
  const { onUser } = p;

  useEffect(() => {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("pair");
    if (!code) return;
    setState("pairing");
    url.searchParams.delete("pair");
    window.history.replaceState(null, "", url.pathname + url.search + url.hash);
    api
      .pairDevice(code, navigator.userAgent.includes("Android") ? "Android phone" : "Elder phone")
      .then((r) => {
        onUser(r.user_id);
        setState("idle");
      })
      .catch(() => setState("failed"));
  }, [onUser]);

  if (state === "pairing") return <p style={{ fontSize: 28, padding: 32 }}>Connecting...</p>;
  if (state === "failed")
    return (
      <p role="alert" style={{ fontSize: 28, padding: 32 }}>
        हा दुवा चालत नाही. घरच्यांना नवीन दुवा मागा.
      </p>
    );
  return <>{p.children}</>;
}
