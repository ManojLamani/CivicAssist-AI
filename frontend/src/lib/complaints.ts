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
export type Receipt = ComplaintInput & { id: string; status: string; created_at: string };

export async function submitComplaint(input: ComplaintInput, submissionId: string): Promise<Receipt> {
  const data = complaintSchema.parse(input);
  const original = useAuth.getState().session;
  if (!original) throw new Error("Sign in before submitting a complaint.");
  await loadCurrentUser();
  const current = useAuth.getState().session;
  if (!current || current.id !== original.id) throw new Error("Your session changed. Sign in and try again.");
  try {
    return await apiRequest<Receipt>("complaints", { ...data, submission_id: submissionId }, current.tokens.access_token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      throw new Error("This submission was already used for another report. Start a new report.");
    }
    throw error;
  }
}
