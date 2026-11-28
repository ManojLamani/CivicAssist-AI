import type { Metadata } from "next";
import { ComplaintsView } from "@/components/complaints-view";

export const metadata: Metadata = { title: "Your complaints | CivicAssist AI" };
export default function Complaints() { return <ComplaintsView />; }
