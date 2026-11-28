import { afterEach, beforeEach, mock, test } from "node:test";
import assert from "node:assert/strict";
import { signIn, useAuth } from "../src/lib/auth.ts";
import { complaintSchema, submitComplaint } from "../src/lib/complaints.ts";

const input = { title: " Damaged road surface ", description: "A broken road surface needs inspection.", category: "roads", location: "Test street near the park" };
const user = { id: "citizen-1", email: "citizen@example.com", full_name: "Citizen", role_name: "citizen" };
const tokens = { access_token: "test-access", refresh_token: "test-refresh", expires_in: 900 };
const reply = (body, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => useAuth.setState({ session: null }));
afterEach(() => mock.restoreAll());

test("complaint validation trims inputs and rejects incomplete or unsupported reports", () => {
  assert.equal(complaintSchema.parse(input).title, "Damaged road surface");
  for (const changes of [{ title: " " }, { description: "short" }, { location: " " }, { category: "invalid" }, { description: "x".repeat(5001) }]) {
    assert.equal(complaintSchema.safeParse({ ...input, ...changes }).success, false);
  }
});

test("signed-out submissions do not make network requests", async () => {
  const fetch = mock.method(globalThis, "fetch", async () => { throw new Error("unexpected request"); });
  await assert.rejects(submitComplaint(input, "draft-1"), /Sign in/);
  assert.equal(fetch.mock.callCount(), 0);
});

test("submission uses the authenticated token and sends a retry key without ownership or status", async () => {
  const receipt = { ...complaintSchema.parse(input), id: "receipt-1", status: "submitted", created_at: "2026-11-28T10:00:00Z" };
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/auth/login")) return reply(tokens);
    if (url.endsWith("/auth/me")) return reply(user);
    assert.ok(url.endsWith("/api/v1/complaints"));
    assert.equal(options.headers.Authorization, "Bearer test-access");
    assert.deepEqual(JSON.parse(options.body), { ...complaintSchema.parse(input), submission_id: "draft-1" });
    return reply(receipt, 201);
  });
  await signIn({ email: user.email, password: "long-test-password" });
  assert.deepEqual(await submitComplaint({ ...input, user_id: "someone-else", status: "resolved" }, "draft-1"), receipt);
});

test("conflicts show a complaint-specific error and failed requests do not claim success", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/auth/login") ? tokens : user));
  await signIn({ email: user.email, password: "long-test-password" });
  mock.restoreAll();
  mock.method(globalThis, "fetch", async url => url.endsWith("/auth/me") ? reply(user) : reply({}, 409));
  await assert.rejects(submitComplaint(input, "draft-1"), /another report/);
});
