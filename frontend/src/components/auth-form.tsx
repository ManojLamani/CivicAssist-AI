"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { authSchema, registerAccount, signIn, type AuthInput } from "@/lib/auth";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const creating = mode === "register";
  const router = useRouter();
  const submitting = useRef(false);
  const [created, setCreated] = useState(false);
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<AuthInput>({
    resolver: zodResolver(authSchema(mode)),
    defaultValues: { email: "", password: "", full_name: "" },
  });

  async function submit(data: AuthInput) {
    if (submitting.current) return;
    submitting.current = true;
    try {
      if (creating) { await registerAccount(data); setCreated(true); }
      else { await signIn(data); router.replace("/account"); }
    } catch (error) {
      setError("root", { message: error instanceof Error ? error.message : "Something went wrong. Please try again." });
    } finally { submitting.current = false; }
  }

  if (created) return <section className="auth-panel" aria-labelledby="created-title">
    <p className="eyebrow">ACCOUNT CREATED</p>
    <h1 id="created-title">You’re ready to sign in.</h1>
    <p>Your citizen account has been created.</p>
    <Link className="button" href="/login">Continue to sign in</Link>
  </section>;

  return <section className="auth-panel" aria-labelledby="auth-title">
    <p className="eyebrow">{creating ? "JOIN CIVICASSIST" : "WELCOME BACK"}</p>
    <h1 id="auth-title">{creating ? "Create your account." : "Sign in."}</h1>
    <p>{creating ? "Start with a citizen account for Bengaluru." : "Use your email and password to continue."}</p>
    <form noValidate onSubmit={handleSubmit(submit)}>
      <fieldset disabled={isSubmitting}>
        {creating && <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input id="full_name" autoComplete="name" maxLength={160} {...register("full_name")}
            aria-invalid={!!errors.full_name} aria-describedby={errors.full_name ? "name-error" : undefined} />
          {errors.full_name && <p className="field-error" id="name-error" role="alert">{errors.full_name.message}</p>}
        </div>}
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" inputMode="email" autoComplete="username" maxLength={320}
            autoCapitalize="none" {...register("email")} aria-invalid={!!errors.email}
            aria-describedby={errors.email ? "email-error" : undefined} />
          {errors.email && <p className="field-error" id="email-error" role="alert">{errors.email.message}</p>}
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete={creating ? "new-password" : "current-password"}
            maxLength={128} {...register("password")} aria-invalid={!!errors.password}
            aria-describedby={errors.password ? "password-error" : creating ? "password-hint" : undefined} />
          {creating && <p id="password-hint" className="hint">Use 12–128 characters.</p>}
          {errors.password && <p className="field-error" id="password-error" role="alert">{errors.password.message}</p>}
        </div>
        {errors.root && <p className="form-error" role="alert">{errors.root.message}</p>}
        <button type="submit" aria-busy={isSubmitting}>
          {isSubmitting ? (creating ? "Creating account…" : "Signing in…") : creating ? "Create account" : "Sign in"}
        </button>
      </fieldset>
    </form>
    <p className="form-switch">{creating ? "Already have an account? " : "New to CivicAssist? "}
      <Link href={creating ? "/login" : "/register"}>{creating ? "Sign in" : "Create an account"}</Link>
    </p>
    {!creating && <p className="hint">You’ll need to sign in again after refreshing the page.</p>}
  </section>;
}
