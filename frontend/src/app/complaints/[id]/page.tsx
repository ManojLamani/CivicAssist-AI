import type { Metadata } from "next";
import { CitizenComplaints } from "@/components/citizen-complaints";

export const metadata: Metadata = { title: "Track complaint | CivicAssist AI" };
export default async function Complaint({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CitizenComplaints complaintId={id} />;
}
