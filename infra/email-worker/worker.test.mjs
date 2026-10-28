import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "./worker.mjs";

const env = {
  INBOUND_DOMAIN: "jobs.yourdomain.com", WEBHOOK_URL: "https://app.example.test/hooks/inbound-mail",
  WEBHOOK_SECRET: "local-test", BACKUP_MAILBOX: "backup@example.test",
};

function message(to = "resumes+acme@jobs.yourdomain.com") {
  const state = { rejects: [], forwarded: [] };
  return { ...state, to, raw: "raw mime", rawSize: 8,
    setReject(reason) { state.rejects.push(reason); },
    async forward(to) { state.forwarded.push(to); },
  };
}

test("nonmatching recipients bounce without forwarding", async () => {
  const mail = message("other@jobs.yourdomain.com");
  await worker.email(mail, env);
  assert.equal(mail.rejects.length, 1);
  assert.equal(mail.forwarded.length, 0);
});

test("raw MIME, secret and envelope recipient go to webhook; backup also receives", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, env.WEBHOOK_URL);
      assert.equal(options.body, "raw mime");
      assert.equal(options.headers["X-Envelope-To"], "resumes+acme@jobs.yourdomain.com");
      assert.equal(options.headers["X-Webhook-Secret"], env.WEBHOOK_SECRET);
      return new Response("ok");
    };
    const mail = message();
    await worker.email(mail, env);
    assert.deepEqual(mail.forwarded, [env.BACKUP_MAILBOX]);
    assert.equal(mail.rejects.length, 0);
  } finally { globalThis.fetch = original; }
});

test("unknown organization gets a real bounce", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response("unknown", { status: 404 });
    const mail = message();
    await worker.email(mail, env);
    assert.equal(mail.rejects.length, 1);
  } finally { globalThis.fetch = original; }
});

test("webhook failure retains backup; failure of both rejects", async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => { throw new Error("offline"); };
    const backedUp = message();
    await worker.email(backedUp, env);
    assert.equal(backedUp.rejects.length, 0);
    const failed = message();
    failed.forward = async () => { throw new Error("offline"); };
    await worker.email(failed, env);
    assert.equal(failed.rejects.length, 1);
  } finally { globalThis.fetch = original; }
});
