import { z } from "zod";
import { ApiError, apiRequest, loadCurrentUser, useAuth } from "./auth.ts";

export const categories = {
  roads: "Roads", garbage: "Garbage", water_supply: "Water supply", drainage: "Drainage",
  streetlights: "Electricity and streetlights", public_infrastructure: "Public infrastructure",
  sanitation: "Sanitation", other: "Other",
} as const;

export const complaintSchema = z.object({
  title: z.string().trim().min(5, "Use at least 5 characters.").max(160),
  description: z.string().trim().min(10, "Describe the issue in at least 10 characters.").max(5000),
  category: z.enum(["roads", "garbage", "water_supply", "drainage", "streetlights", "public_infrastructure", "sanitation", "other"]),
  location: z.string().trim().min(5, "Enter a street, area, or nearby landmark.").max(500),
});
export type ComplaintInput = z.infer<typeof complaintSchema>;
export const complaintStatuses = ["submitted", "acknowledged", "in_progress", "resolved", "closed"] as const;
export type ComplaintStatus = typeof complaintStatuses[number];
export type StatusEvent = { id: number; from_status: string | null; to_status: string; note: string; created_at: string };
export type Receipt = ComplaintInput & { id: string; status: string; created_at: string; history?: StatusEvent[] };
export type AdminComplaint = Receipt & { allowed_statuses: ComplaintStatus[] };
export const statusUpdateSchema = z.object({
  status: z.enum(complaintStatuses), note: z.string().trim().min(1, "Explain the status change.").max(1000),
});
export type StatusUpdate = z.infer<typeof statusUpdateSchema>;
export function statusLabel(value: string) { return value.replaceAll("_", " ").replace(/^./, c => c.toUpperCase()); }
export type ComplaintSummary = Pick<Receipt, "id" | "title" | "category" | "status" | "created_at">;
export type ComplaintPage = { items: ComplaintSummary[]; total: number; limit: number; offset: number };

async function complaintRequest<T>(path: string, body?: object, method?: "PATCH"): Promise<T> {
  const original = useAuth.getState().session;
  if (!original) throw new Error("Sign in to access your complaints.");
  await loadCurrentUser();
  const current = useAuth.getState().session;
  if (!current || current.id !== original.id) throw new Error("Your session changed. Sign in and try again.");
  return apiRequest<T>(path, body, current.tokens.access_token, method);
}

export function listComplaints(offset = 0, admin = false): Promise<ComplaintPage> {
  return complaintRequest<ComplaintPage>(`${admin ? "admin/" : ""}complaints?limit=20&offset=${offset}`);
}

export function getComplaint(id: string, admin = false): Promise<Receipt | AdminComplaint> {
  if (!z.string().uuid().safeParse(id).success) return Promise.reject(new Error("Complaint not found."));
  return complaintRequest<Receipt | AdminComplaint>(`${admin ? "admin/" : ""}complaints/${id}`).catch(error => {
    if (error instanceof ApiError && error.status === 404) throw new Error("Complaint not found.");
    throw error;
  });
}

export async function updateComplaintStatus(id: string, expectedStatus: string, input: StatusUpdate): Promise<AdminComplaint> {
  z.string().uuid().parse(id);
  const data = statusUpdateSchema.parse(input);
  try {
    return await complaintRequest<AdminComplaint>(`admin/complaints/${id}/status`,
      { ...data, expected_status: expectedStatus }, "PATCH");
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      throw new Error("This complaint changed or the transition is not allowed. Refresh and review before trying again.");
    }
    throw error;
  }
}

export async function submitComplaint(input: ComplaintInput, submissionId: string): Promise<Receipt> {
  const data = complaintSchema.parse(input);
  try {
    return await complaintRequest<Receipt>("complaints", { ...data, submission_id: submissionId });
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      throw new Error("This submission was already used for another report. Start a new report.");
    }
    throw error;
  }
}
