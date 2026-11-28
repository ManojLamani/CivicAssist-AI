import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Create account | CivicAssist AI" };
export default function Register() { return <AuthForm mode="register" />; }
