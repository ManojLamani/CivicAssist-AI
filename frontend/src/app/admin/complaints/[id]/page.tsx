import type { Metadata } from "next";
import { ComplaintsView } from "@/components/complaints-view";

export const metadata: Metadata = { title: "Review complaint | CivicAssist AI" };
export default async function AdminComplaint({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ComplaintsView admin complaintId={id} />;
}
