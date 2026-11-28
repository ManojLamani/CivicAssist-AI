import { afterEach, beforeEach, mock, test } from "node:test";
import assert from "node:assert/strict";
import { signIn, useAuth } from "../src/lib/auth.ts";
import { complaintSchema, getComplaint, listComplaints, statusUpdateSchema, submitComplaint, updateComplaintStatus } from "../src/lib/complaints.ts";

const input = { title: " Damaged road surface ", description: "A broken road surface needs inspection.", category: "roads", location: "Test street near the park" };
const user = { id: "citizen-1", email: "citizen@example.com", full_name: "Citizen", role_name: "citizen" };
const tokens = { access_token: "test-access", refresh_token: "test-refresh", expires_in: 900 };
const reply = (body, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => useAuth.setState({ session: null }));
afterEach(() => mock.restoreAll());

test("admin reads and updates use protected routes and the status last viewed", async () => {
  const id = "63e0b8ae-7eb7-41c0-84b3-7c27c554c50f";
  const admin = { ...user, role_name: "administrator" };
  const updated = { id, status: "acknowledged", allowed_statuses: ["in_progress"], history: [{ id: 2, note: "Report reviewed." }] };
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/auth/login")) return reply(tokens);
    if (url.endsWith("/auth/me")) return reply(admin);
    assert.equal(options.headers.Authorization, "Bearer test-access");
    assert.ok(url.includes("/api/v1/admin/complaints"));
    if (options.method === "PATCH") {
      assert.ok(url.endsWith(`/${id}/status`));
      assert.deepEqual(JSON.parse(options.body), { status: "acknowledged", expected_status: "submitted", note: "Report reviewed." });
      return reply(updated);
    }
    assert.equal(options.method, "GET");
    return reply(url.includes("?") ? { items: [], total: 0, limit: 20, offset: 0 } : updated);
  });
  await signIn({ email: user.email, password: "long-test-password" });
  assert.equal((await listComplaints(0, true)).total, 0);
  assert.deepEqual(await getComplaint(id, true), updated);
  assert.deepEqual(await updateComplaintStatus(id, "submitted", { status: "acknowledged", note: " Report reviewed. " }), updated);
});

test("status notes are required and stale updates show a refresh instruction", async () => {
  for (const input of [{ status: "resolved", note: " " }, { status: "resolved", note: "x".repeat(1001) }, { status: "assigned", note: "Reviewed." }]) {
    assert.equal(statusUpdateSchema.safeParse(input).success, false);
  }
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/auth/login") ? tokens : user));
  await signIn({ email: user.email, password: "long-test-password" });
  mock.restoreAll();
  mock.method(globalThis, "fetch", async url => url.endsWith("/auth/me") ? reply(user) : reply({}, 409));
  await assert.rejects(updateComplaintStatus("63e0b8ae-7eb7-41c0-84b3-7c27c554c50f", "submitted", { status: "acknowledged", note: "Reviewed." }), /Refresh and review/);
});

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

test("listing and tracking use authenticated GET requests without accepting an owner override", async () => {
  const id = "63e0b8ae-7eb7-41c0-84b3-7c27c554c50f";
  const receipt = { ...complaintSchema.parse(input), id, status: "submitted", created_at: "2026-11-28T10:00:00Z" };
  const page = { items: [receipt], total: 21, limit: 20, offset: 20 };
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/auth/login")) return reply(tokens);
    if (url.endsWith("/auth/me")) return reply(user);
    assert.equal(options.method, "GET");
    assert.equal(options.headers.Authorization, "Bearer test-access");
    assert.equal(options.body, undefined);
    if (url.endsWith("/complaints?limit=20&offset=20")) return reply(page);
    assert.ok(url.endsWith(`/complaints/${id}`));
    return reply(receipt);
  });
  await signIn({ email: user.email, password: "long-test-password" });
  assert.deepEqual(await listComplaints(20), page);
  assert.deepEqual(await getComplaint(id), receipt);
});

test("signed-out reads do not make requests and malformed tracking IDs cannot form paths", async () => {
  const fetch = mock.method(globalThis, "fetch", async () => { throw new Error("unexpected request"); });
  await assert.rejects(listComplaints(), /Sign in/);
  await assert.rejects(getComplaint("63e0b8ae-7eb7-41c0-84b3-7c27c554c50f"), /Sign in/);
  await assert.rejects(getComplaint("../auth/me"), /not found/);
  assert.equal(fetch.mock.callCount(), 0);
});

test("tracking not-found and network failures are not treated as empty lists", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/auth/login") ? tokens : user));
  await signIn({ email: user.email, password: "long-test-password" });
  mock.restoreAll();
  mock.method(globalThis, "fetch", async url => url.endsWith("/auth/me") ? reply(user) : reply({}, 404));
  await assert.rejects(getComplaint("63e0b8ae-7eb7-41c0-84b3-7c27c554c50f"), /not found/);
  mock.restoreAll();
  mock.method(globalThis, "fetch", async () => { throw new TypeError("network"); });
  await assert.rejects(listComplaints(), /Could not reach/);
});
