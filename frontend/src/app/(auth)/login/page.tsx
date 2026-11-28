import type { Metadata } from "next";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Sign in | CivicAssist AI" };
export default function Login() { return <AuthForm mode="login" />; }
