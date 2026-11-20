import { useCallback, useEffect, useState } from "react";

import { api } from "../api";

type Dev = { id: number; label: string; last_seen: string | null; revoked: boolean };

/** Family: make a one-time link (15 min) that connects ONE phone to this elder, and revoke phones. */
export function PairCard(p: { userId: number }) {
  const [link, setLink] = useState<{ url: string; code: string; expires_at: string } | null>(null);
  const [devices, setDevices] = useState<Dev[]>([]);
  const [err, setErr] = useState("");
  const { userId } = p;

  const load = useCallback(async () => {
    try {
      setDevices(await api.pairedDevices(userId));
    } catch {
      setDevices([]); // auth off, or not an owner: nothing to show
    }
  }, [userId]);
  useEffect(() => {
    setLink(null);
    void load();
  }, [load]);

  const make = async () => {
    setErr("");
    try {
      const l = await api.pairingLink(userId);
      setLink({ ...l, url: l.url.startsWith("http") ? l.url : `${window.location.origin}${l.url}` });
    } catch {
      setErr("Could not make a link. Log in again.");
    }
  };
  const revoke = async (id: number) => {
    await api.revokeDevice(userId, id);
    await load();
  };

  return (
    <section className="fam-card" aria-label="Elder phone link">
      <h2>Connect the elder's phone</h2>
      <p>Open this one-time link on her phone (valid 15 minutes, works once). Only that phone can talk to her Arjun.</p>
      <button className="fbtn" onClick={() => void make()}>
        Create elder link
      </button>
      {err && <p role="alert">{err}</p>}
      {link && (
        <p>
          <input className="fam-input" readOnly value={link.url} onFocus={(e) => e.currentTarget.select()} style={{ width: "100%" }} />
          <br />
          Code: <b>{link.code}</b>
        </p>
      )}
      {devices.length > 0 && (
        <ul>
          {devices.map((d) => (
            <li key={d.id}>
              {d.label} {d.revoked ? "(removed)" : ""}
              {!d.revoked && (
                <button className="fbtn" style={{ marginLeft: 8 }} onClick={() => void revoke(d.id)}>
                  Remove phone
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
