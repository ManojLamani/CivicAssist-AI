"use client";

import { useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { statusLabel, statusUpdateSchema, updateComplaintStatus, type AdminComplaint, type StatusUpdate } from "@/lib/complaints";

export function StatusUpdateForm({ complaint, onUpdated }: { complaint: AdminComplaint; onUpdated: (data: AdminComplaint) => void }) {
  const pending = useRef(false);
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<StatusUpdate>({
    resolver: zodResolver(statusUpdateSchema),
    defaultValues: { status: complaint.allowed_statuses[0] ?? "closed", note: "" },
  });
  async function submit(input: StatusUpdate) {
    if (pending.current) return;
    pending.current = true;
    try { onUpdated(await updateComplaintStatus(complaint.id, complaint.status, input)); }
    catch (error) { setError("root", { message: error instanceof Error ? error.message : "Could not update status." }); }
    finally { pending.current = false; }
  }
  if (complaint.allowed_statuses.length === 0) return <p className="hint">This complaint is closed. No further status changes are available.</p>;
  return <form noValidate onSubmit={handleSubmit(submit)} aria-label="Update complaint status">
    <h2>Update status</h2>
    <fieldset disabled={isSubmitting}>
      <div className="field"><label htmlFor="next-status">New status</label>
        <select id="next-status" {...register("status")} aria-invalid={!!errors.status}>
          {complaint.allowed_statuses.map(status => <option key={status} value={status}>{statusLabel(status)}</option>)}
        </select>
        {errors.status && <p role="alert" className="field-error">{errors.status.message}</p>}
      </div>
      <div className="field"><label htmlFor="status-note">Update note (visible to the citizen)</label>
        <textarea id="status-note" rows={3} maxLength={1000} {...register("note")} aria-invalid={!!errors.note} aria-describedby={errors.note ? "note-error" : undefined} />
        {errors.note && <p id="note-error" role="alert" className="field-error">{errors.note.message}</p>}
      </div>
      {errors.root && <p role="alert" className="form-error">{errors.root.message}</p>}
      <button type="submit" aria-busy={isSubmitting}>{isSubmitting ? "Saving…" : "Save status update"}</button>
    </fieldset>
  </form>;
}
