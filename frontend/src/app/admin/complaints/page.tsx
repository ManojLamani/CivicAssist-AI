import type { Metadata } from "next";
import { ComplaintsView } from "@/components/complaints-view";

export const metadata: Metadata = { title: "Complaint queue | CivicAssist AI" };
export default function AdminComplaints() { return <ComplaintsView admin />; }
