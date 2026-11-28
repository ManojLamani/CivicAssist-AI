import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { mock } from "node:test";
import { authSchema, registerAccount, signIn, loadCurrentUser, signOut, useAuth } from "../src/lib/auth.ts";

const user = { id: "user-1", email: "citizen@example.com", full_name: "Citizen", role_name: "citizen" };
const tokens = { access_token: "access-1", refresh_token: "refresh-1", expires_in: 900 };
const input = { email: " Citizen@Example.com ", password: "long-test-password", full_name: " Citizen " };
const reply = (body, status = 200) => new Response(status === 204 ? null : JSON.stringify(body), { status });

beforeEach(() => useAuth.setState({ session: null }));
afterEach(() => mock.restoreAll());

test("validation normalizes identity fields and preserves password whitespace", () => {
  const parsed = authSchema("register").parse({ ...input, password: " padded-password " });
  assert.equal(parsed.email, user.email);
  assert.equal(parsed.full_name, "Citizen");
  assert.equal(parsed.password, " padded-password ");
  assert.equal(authSchema("register").safeParse({ ...input, password: "short" }).success, false);
  assert.equal(authSchema("register").safeParse({ ...input, full_name: " " }).success, false);
  assert.equal(authSchema("login").safeParse({ ...input, email: "invalid" }).success, false);
});

test("registration sends reviewed fields without role assignment", async () => {
  const fetch = mock.method(globalThis, "fetch", async (_, options) => {
    assert.deepEqual(JSON.parse(options.body), { email: user.email, password: input.password, full_name: "Citizen" });
    return reply(user, 201);
  });
  await registerAccount({ ...input, role_name: "administrator" });
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(useAuth.getState().session, null);
});

test("login verifies the current user and logout revokes the saved refresh token", async () => {
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/login")) {
      assert.deepEqual(JSON.parse(options.body), { email: user.email, password: input.password });
      return reply(tokens);
    }
    if (url.endsWith("/logout")) {
      assert.deepEqual(JSON.parse(options.body), { refresh_token: tokens.refresh_token });
      return reply(null, 204);
    }
    assert.equal(options.headers.Authorization, `Bearer ${tokens.access_token}`);
    return reply(user);
  });
  await signIn(input);
  assert.deepEqual(useAuth.getState().session.user, user);
  await signOut();
  assert.equal(useAuth.getState().session, null);
});

test("login and registration errors are understandable and do not store a session", async () => {
  mock.method(globalThis, "fetch", async () => reply({}, 401));
  await assert.rejects(signIn(input), /incorrect/);
  assert.equal(useAuth.getState().session, null);
  mock.restoreAll();
  mock.method(globalThis, "fetch", async () => reply({}, 409));
  await assert.rejects(registerAccount(input), /already registered/);
});

test("network errors are shown without claiming logout succeeded", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/login") ? tokens : user));
  await signIn(input);
  mock.restoreAll();
  mock.method(globalThis, "fetch", async () => { throw new TypeError("network"); });
  await assert.rejects(signOut(), /Could not reach/);
  assert.ok(useAuth.getState().session);
});

test("concurrent expired requests share one refresh and save the replacement token", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/login") ? tokens : user));
  await signIn(input);
  mock.restoreAll();
  let refreshes = 0;
  const rotated = { ...tokens, access_token: "access-2", refresh_token: "refresh-2" };
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/refresh")) {
      refreshes++;
      assert.deepEqual(JSON.parse(options.body), { refresh_token: "refresh-1" });
      await new Promise(resolve => setTimeout(resolve, 10));
      return reply(rotated);
    }
    return options.headers.Authorization === "Bearer access-1" ? reply({}, 401) : reply(user);
  });
  await Promise.all([loadCurrentUser(), loadCurrentUser()]);
  assert.equal(refreshes, 1);
  assert.equal(useAuth.getState().session.tokens.refresh_token, "refresh-2");
});

test("rejected refresh clears the expired local session", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/login") ? tokens : user));
  await signIn(input);
  mock.restoreAll();
  mock.method(globalThis, "fetch", async () => reply({}, 401));
  await assert.rejects(loadCurrentUser(), /expired/);
  assert.equal(useAuth.getState().session, null);
});

test("an in-flight refresh cannot restore a logged-out session", async () => {
  mock.method(globalThis, "fetch", async url => reply(url.endsWith("/login") ? tokens : user));
  await signIn(input);
  mock.restoreAll();
  let release, started;
  const ready = new Promise(resolve => { started = resolve; });
  mock.method(globalThis, "fetch", async (url, options) => {
    if (url.endsWith("/logout")) return reply(null, 204);
    if (url.endsWith("/refresh")) { started(); return new Promise(resolve => { release = resolve; }); }
    return options.headers.Authorization === "Bearer access-1" ? reply({}, 401) : reply(user);
  });
  const pending = loadCurrentUser();
  await ready;
  await signOut();
  release(reply({ ...tokens, access_token: "access-2", refresh_token: "refresh-2" }));
  await pending;
  assert.equal(useAuth.getState().session, null);
});
