"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useAuth } from "@/lib/auth";
import { categories, complaintSchema, statusLabel, submitComplaint, type ComplaintInput, type Receipt } from "@/lib/complaints";

export default function NewComplaint() {
  const session = useAuth(state => state.session);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const pending = useRef(false);
  const receiptHeading = useRef<HTMLHeadingElement>(null);
  const draft = useRef<{ signature: string; id: string } | null>(null);
  const { register, handleSubmit, setError, reset, formState: { errors, isSubmitting } } = useForm<ComplaintInput>({
    resolver: zodResolver(complaintSchema),
    defaultValues: { title: "", description: "", category: "other", location: "" },
  });

  useEffect(() => { if (receipt) receiptHeading.current?.focus(); }, [receipt]);

  async function submit(data: ComplaintInput) {
    if (pending.current) return;
    pending.current = true;
    const signature = JSON.stringify(data);
    if (draft.current?.signature !== signature) draft.current = { signature, id: crypto.randomUUID() };
    try { setReceipt(await submitComplaint(data, draft.current.id)); }
    catch (error) { setError("root", { message: error instanceof Error ? error.message : "Could not submit your report." }); }
    finally { pending.current = false; }
  }

  if (!session) return <section className="account-panel">
    <h1>Sign in to report an issue.</h1>
    <p>A citizen account is required to submit a complaint.</p>
    <Link className="button" href="/login">Sign in</Link>
  </section>;

  if (session.user.role_name !== "citizen") return <section className="account-panel">
    <h1>A citizen account is required.</h1>
    <Link href="/account">Back to account</Link>
  </section>;

  if (receipt) return <section className="account-panel" aria-labelledby="receipt-title">
    <p className="eyebrow">REPORT SAVED</p>
    <h1 id="receipt-title" tabIndex={-1} ref={receiptHeading}>Your complaint is submitted.</h1>
    <p>Keep this complaint ID for your records:</p>
    <p className="receipt-id">{receipt.id}</p>
    <dl className="receipt-details">
      <dt>Issue</dt><dd>{receipt.title}</dd>
      <dt>Category</dt><dd>{categories[receipt.category]}</dd>
      <dt>Location</dt><dd>{receipt.location}</dd>
      <dt>Status</dt><dd>{statusLabel(receipt.status)}</dd>
      <dt>Saved at</dt><dd>{new Date(receipt.created_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</dd>
    </dl>
    <p className="hint">Saved in CivicAssist. This does not send a report to a government department.</p>
    <p><Link className="button" href={`/complaints/${receipt.id}`}>Track this complaint</Link></p>
    <button onClick={() => { reset(); draft.current = null; setReceipt(null); }}>Report another issue</button>
    <p><Link href="/account">Back to account</Link></p>
  </section>;

  return <section className="account-panel" aria-labelledby="complaint-title">
    <p className="eyebrow">CITIZEN REPORT</p>
    <h1 id="complaint-title">Report a civic issue.</h1>
    <p>Describe what needs attention and where it is.</p>
    <p className="hint">Reports stay in CivicAssist; government delivery is not connected.</p>
    <form noValidate onSubmit={handleSubmit(submit)}>
      <fieldset disabled={isSubmitting}>
        <div className="field">
          <label htmlFor="title">Issue title</label>
          <input id="title" maxLength={160} {...register("title")} aria-invalid={!!errors.title} aria-describedby={errors.title ? "title-error" : undefined} />
          {errors.title && <p id="title-error" className="field-error" role="alert">{errors.title.message}</p>}
        </div>
        <div className="field">
          <label htmlFor="category">Category</label>
          <select id="category" {...register("category")} aria-invalid={!!errors.category} aria-describedby={errors.category ? "category-error" : undefined}>
            {Object.entries(categories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
          {errors.category && <p id="category-error" className="field-error" role="alert">{errors.category.message}</p>}
        </div>
        <div className="field">
          <label htmlFor="description">Describe the problem</label>
          <textarea id="description" rows={5} maxLength={5000} {...register("description")} aria-invalid={!!errors.description} aria-describedby={errors.description ? "description-error" : undefined} />
          {errors.description && <p id="description-error" className="field-error" role="alert">{errors.description.message}</p>}
        </div>
        <div className="field">
          <label htmlFor="location">Location or landmark</label>
          <input id="location" maxLength={500} {...register("location")} aria-invalid={!!errors.location} aria-describedby={errors.location ? "location-error" : "location-hint"} />
          <p id="location-hint" className="hint">Include a street, area, or nearby landmark in Bengaluru.</p>
          {errors.location && <p id="location-error" className="field-error" role="alert">{errors.location.message}</p>}
        </div>
        {errors.root && <p className="form-error" role="alert">{errors.root.message}</p>}
        <button type="submit" aria-busy={isSubmitting}>{isSubmitting ? "Submitting…" : "Submit complaint"}</button>
      </fieldset>
    </form>
    <p><Link href="/account">Back to account</Link></p>
  </section>;
}
