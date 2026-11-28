"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { loadCurrentUser, signOut, useAuth } from "@/lib/auth";

export default function Account() {
  const session = useAuth(state => state.session);
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    loadCurrentUser().catch(error => {
      if (active) setError(error instanceof Error ? error.message : "Could not check your session.");
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, []);

  async function logout() {
    setBusy(true); setError("");
    try { await signOut(); router.replace("/login"); }
    catch { setError("Could not sign out. Check your connection and try again."); }
    finally { setBusy(false); }
  }

  if (checking) return <section className="account-panel"><p role="status">Checking your session…</p></section>;
  if (!session) return <section className="account-panel">
    <h1>Sign in to continue.</h1>
    {error && <p role="alert" className="form-error">{error}</p>}
    <Link className="button" href="/login">Sign in</Link>
  </section>;

  return <section className="account-panel">
    <p className="eyebrow">YOUR ACCOUNT</p>
    <h1>Welcome, {session.user.full_name}.</h1>
    <p>Signed in as <strong>{session.user.email}</strong>.</p>
    {session.user.role_name === "administrator" ? <p><Link className="button" href="/admin/complaints">Manage complaints</Link></p> :
      session.user.role_name === "citizen" && <><p><Link className="button" href="/complaints/new">Report a civic issue</Link></p>
        <p><Link href="/complaints">View my complaints</Link></p></>}
    <p className="hint">Refreshing this page will require you to sign in again.</p>
    {error && <p role="alert" className="form-error">{error}</p>}
    <button disabled={busy} onClick={logout}>{busy ? "Signing out…" : "Sign out"}</button>
  </section>;
}
