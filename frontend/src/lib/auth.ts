import { create } from "zustand";
import { z } from "zod";

export function authSchema(mode: "login" | "register") {
  return z.object({
    email: z.string().trim().toLowerCase().email("Enter a valid email address.").max(320),
    password: z.string().min(mode === "register" ? 12 : 1,
      mode === "register" ? "Use at least 12 characters." : "Enter your password.").max(128),
    full_name: z.string().trim().max(160).optional(),
  }).superRefine((data, ctx) => {
    if (mode === "register" && !data.full_name) {
      ctx.addIssue({ code: "custom", path: ["full_name"], message: "Enter your full name." });
    }
  });
}

export type AuthInput = z.infer<ReturnType<typeof authSchema>>;
export type User = { id: string; email: string; full_name: string; role_name: string };
type Tokens = { access_token: string; refresh_token: string; expires_in: number };
type Session = { id: string; user: User; tokens: Tokens };

// Deliberately not persisted: tokens never enter localStorage, sessionStorage, or URLs.
export const useAuth = create<{ session: Session | null }>(() => ({ session: null }));

class ApiError extends Error {
  status: number;
  constructor(status: number) {
    super(status === 401 ? "Email or password is incorrect, or your session has expired."
      : status === 409 ? "This email is already registered. Please sign in."
      : status === 422 ? "Check your details and try again."
      : "The service is unavailable. Please try again.");
    this.status = status;
  }
}

async function request<T>(path: string, body?: object, accessToken?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/auth/${path}`, {
      method: body ? "POST" : "GET", cache: "no-store", signal: AbortSignal.timeout(10_000),
      headers: { ...(body && { "Content-Type": "application/json" }),
        ...(accessToken && { Authorization: `Bearer ${accessToken}` }) },
      ...(body && { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error("Could not reach CivicAssist. Check your connection and try again.");
  }
  if (!response.ok) throw new ApiError(response.status);
  return response.status === 204 ? undefined as T : response.json();
}

export async function registerAccount(input: AuthInput) {
  const data = authSchema("register").parse(input);
  await request<User>("register", data);
}

export async function signIn(input: AuthInput) {
  const { email, password } = authSchema("login").parse(input);
  const tokens = await request<Tokens>("login", { email, password });
  const user = await request<User>("me", undefined, tokens.access_token);
  useAuth.setState({ session: { id: crypto.randomUUID(), user, tokens } });
}

let refreshInFlight: { id: string; promise: Promise<Tokens> } | null = null;

export async function loadCurrentUser() {
  const original = useAuth.getState().session;
  if (!original) return null;
  try {
    let user: User;
    try {
      user = await request<User>("me", undefined, original.tokens.access_token);
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      const current = useAuth.getState().session;
      if (current?.id !== original.id) return null;
      let tokens = current.tokens;
      if (tokens.access_token === original.tokens.access_token) {
        if (refreshInFlight?.id !== original.id) {
          const promise = request<Tokens>("refresh", { refresh_token: current.tokens.refresh_token })
          .then(tokens => {
            if (useAuth.getState().session?.id === original.id) {
              useAuth.setState({ session: { ...current, tokens } });
            }
            return tokens;
          }).finally(() => { if (refreshInFlight?.id === original.id) refreshInFlight = null; });
          refreshInFlight = { id: original.id, promise };
        }
        tokens = await refreshInFlight.promise;
      }
      user = await request<User>("me", undefined, tokens.access_token);
    }
    const current = useAuth.getState().session;
    if (current?.id === original.id) useAuth.setState({ session: { ...current, user } });
    return user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && useAuth.getState().session?.id === original.id) {
      useAuth.setState({ session: null });
    }
    throw error;
  }
}

export async function signOut() {
  const current = useAuth.getState().session;
  if (current) await request<void>("logout", { refresh_token: current.tokens.refresh_token });
  if (useAuth.getState().session?.id === current?.id) useAuth.setState({ session: null });
}
