"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { categories, getComplaint, listComplaints, statusLabel, type AdminComplaint, type ComplaintPage, type Receipt } from "@/lib/complaints";
import { StatusUpdateForm } from "@/components/status-update-form";

function submittedAt(value: string) {
  return new Date(value).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" }) + " IST";
}

export function ComplaintsView({ complaintId, admin = false }: { complaintId?: string; admin?: boolean }) {
  const session = useAuth(state => state.session);
  const sessionId = session?.id;
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const key = `${sessionId}:${admin}:${complaintId ?? "list"}:${offset}:${refresh}`;
  const [result, setResult] = useState<{ key: string; data?: ComplaintPage | Receipt | AdminComplaint; error?: string; message?: string } | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let active = true;
    const request = complaintId ? getComplaint(complaintId, admin) : listComplaints(offset, admin);
    request.then(data => { if (active) setResult({ key, data }); })
      .catch(error => { if (active) setResult({ key, error: error instanceof Error ? error.message : "Could not load your complaints." }); });
    return () => { active = false; };
  }, [sessionId, complaintId, offset, refresh, key, admin]);

  if (!session) return <section className="account-panel">
    <h1>Sign in to view your complaints.</h1><Link className="button" href="/login">Sign in</Link>
  </section>;
  if (session.user.role_name !== (admin ? "administrator" : "citizen")) return <section className="account-panel">
    <h1>{admin ? "Administrator access is required." : "A citizen account is required."}</h1><Link href="/account">Back to account</Link>
  </section>;

  const current = result?.key === key ? result : null;
  const data = current?.data;
  const loading = !current;
  const base = admin ? "/admin/complaints" : "/complaints";

  return <section className="account-panel" aria-labelledby="complaints-heading">
    <p className="eyebrow">{admin ? "ADMINISTRATION" : "YOUR REPORTS"}</p>
    <h1 id="complaints-heading">{complaintId ? (admin ? "Review complaint." : "Track your complaint.") : admin ? "Complaint queue." : "Your complaints."}</h1>
    <div className="complaint-actions">
      <Link href={complaintId ? base : admin ? "/account" : "/complaints/new"}>{complaintId ? "Back to complaints" : admin ? "Back to account" : "Report a civic issue"}</Link>
      <button disabled={loading} onClick={() => setRefresh(value => value + 1)}>Refresh</button>
    </div>
    {loading && <p role="status">Loading your {complaintId ? "complaint" : "complaints"}…</p>}
    {current?.error && <p className="form-error" role="alert">{current.error}</p>}
    {current?.message && <p role="status">{current.message}</p>}
    {data && "items" in data && <>
      <p role="status">{data.total} {data.total === 1 ? "complaint" : "complaints"} saved.</p>
      {data.items.length === 0 ? <p>{offset === 0 ? (admin ? "No complaints have been submitted yet." : "You haven’t submitted any complaints yet.") : "No complaints on this page. Go back to the previous page."}</p> :
        <ul className="complaint-list">{data.items.map(complaint => <li key={complaint.id}>
          <Link href={`${base}/${complaint.id}`}>{complaint.title}</Link>
          <p className="hint">{categories[complaint.category]} · {statusLabel(complaint.status)} · {submittedAt(complaint.created_at)}</p>
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
        <dt>Current status</dt><dd>{statusLabel(data.status)}</dd>
        <dt>Submitted at</dt><dd>{submittedAt(data.created_at)}</dd>
        <dt>Category</dt><dd>{categories[data.category]}</dd>
        <dt>Location</dt><dd>{data.location}</dd>
      </dl>
      <h2>Description</h2><p className="complaint-description">{data.description}</p>
      {data.history && <><h2>Status history</h2><ol className="complaint-list">{data.history.map(event => <li key={event.id}>
        <strong>{statusLabel(event.to_status)}</strong><p className="hint">{submittedAt(event.created_at)}</p>
        <p className="complaint-description">{event.note}</p>
      </li>)}</ol></>}
      {admin && "allowed_statuses" in data && <StatusUpdateForm key={`${data.id}:${data.status}`} complaint={data}
        onUpdated={updated => { if (useAuth.getState().session?.id === sessionId) setResult({ key, data: updated, message: "Status updated." }); }} />}
      <p className="hint">This report stays in CivicAssist; government delivery is not connected.</p>
    </>}
    <p><Link href="/account">Back to account</Link></p>
  </section>;
}
