"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { categories, getComplaint, listComplaints, type ComplaintPage, type Receipt } from "@/lib/complaints";

function submittedAt(value: string) {
  return new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST";
}

export function CitizenComplaints({ complaintId }: { complaintId?: string }) {
  const session = useAuth(state => state.session);
  const sessionId = session?.id;
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const key = `${sessionId}:${complaintId ?? "list"}:${offset}:${refresh}`;
  const [result, setResult] = useState<{ key: string; data?: ComplaintPage | Receipt; error?: string } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    const request = complaintId ? getComplaint(complaintId) : listComplaints(offset);
    request.then(data => { if (active) setResult({ key, data }); })
      .catch(error => { if (active) setResult({ key, error: error instanceof Error ? error.message : "Could not load your complaints." }); });
    return () => { active = false; };
  }, [sessionId, complaintId, offset, refresh, key]);

  if (!session) return <section className="account-panel">
    <h1>Sign in to view your complaints.</h1><Link className="button" href="/login">Sign in</Link>
  </section>;
  if (session.user.role_name !== "citizen") return <section className="account-panel">
    <h1>A citizen account is required.</h1><Link href="/account">Back to account</Link>
  </section>;

  const current = result?.key === key ? result : null;
  const data = current?.data;
  const loading = !current;

  return <section className="account-panel" aria-labelledby="complaints-heading">
    <p className="eyebrow">YOUR REPORTS</p>
    <h1 id="complaints-heading">{complaintId ? "Track your complaint." : "Your complaints."}</h1>
    <div className="complaint-actions">
      <Link href={complaintId ? "/complaints" : "/complaints/new"}>{complaintId ? "Back to complaints" : "Report a civic issue"}</Link>
      <button disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button>
    </div>
    {loading && <p role="status">Loading your {complaintId ? "complaint" : "complaints"}…</p>}
    {current?.error && <p className="form-error" role="alert">{current.error}</p>}
    {data && "items" in data && <>
      <p role="status">{data.total} {data.total === 1 ? "complaint" : "complaints"} saved.</p>
      {data.items.length === 0 ? <p>{offset === 0 ? "You haven’t submitted any complaints yet." : "No complaints on this page. Go back to the previous page."}</p> :
        <ul className="complaint-list">{data.items.map(complaint => <li key={complaint.id}>
          <Link href={`/complaints/${complaint.id}`}>{complaint.title}</Link>
          <p className="hint">{categories[complaint.category]} · {complaint.status.replaceAll("_", " ")} · {submittedAt(complaint.created_at)}</p>
          <p className="complaint-reference">{complaint.id}</p>
        </li>)}</ul>}
      <div className="complaint-actions" aria-label="Complaint pages">
        <button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - data.limit))}>Previous</button>
        <button disabled={offset + data.items.length >= data.total} onClick={() => setOffset(value => value + data.limit)}>Next</button>
      </div>
    </>}
    {data && !("items" in data) && <>
      <h2>{data.title}</h2>
      <p className="receipt-id">{data.id}</p>
      <dl className="receipt-details">
        <dt>Current status</dt><dd>{data.status.replaceAll("_", " ")}</dd>
        <dt>Submitted at</dt><dd>{submittedAt(data.created_at)}</dd>
        <dt>Category</dt><dd>{categories[data.category]}</dd>
        <dt>Location</dt><dd>{data.location}</dd>
      </dl>
      <h2>Description</h2><p className="complaint-description">{data.description}</p>
      <p className="hint">Status updates beyond submission are not available yet. This report stays in CivicAssist; government delivery is not connected.</p>
    </>}
    <p><Link href="/account">Back to account</Link></p>
  </section>;
}
