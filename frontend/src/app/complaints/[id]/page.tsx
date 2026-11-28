import type { Metadata } from "next";
import { ComplaintsView } from "@/components/complaints-view";

export const metadata: Metadata = { title: "Track complaint | CivicAssist AI" };
export default async function Complaint({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ComplaintsView complaintId={id} />;
}
