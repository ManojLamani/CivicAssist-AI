import type { Metadata } from "next";
import { CitizenComplaints } from "@/components/citizen-complaints";

export const metadata: Metadata = { title: "Your complaints | CivicAssist AI" };
export default function Complaints() { return <CitizenComplaints />; }
