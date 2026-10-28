/** No MIME parsing here: durable ingestion and safety checks run in Python. */
export default {
  async email(message, env) {
    const [local, domain] = message.to.toLowerCase().split("@");
    if (domain !== env.INBOUND_DOMAIN || !/^resumes\+[a-z0-9-]+$/.test(local ?? "")) {
      message.setReject("Unknown recipient");
      return;
    }
    if (message.rawSize > 25 * 1024 * 1024) {
      message.setReject("Message too large");
      return;
    }
    const results = await Promise.allSettled([
      fetch(env.WEBHOOK_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Webhook-Secret": env.WEBHOOK_SECRET,
          "X-Envelope-To": message.to,
        },
        body: message.raw,
      }),
      message.forward(env.BACKUP_MAILBOX),
    ]);
    const delivery = results[0];
    if (delivery.status === "fulfilled" && delivery.value.status === 404) {
      message.setReject("Unknown recipient");
    } else if (delivery.status !== "fulfilled" || !delivery.value.ok) {
      // Backup delivery makes manual replay possible even when this webhook is down.
      console.error("Inbound webhook unavailable; backup status:", results[1].status);
      if (results[1].status !== "fulfilled") {
        message.setReject("Unable to store message; please resend later");
      }
    }
  },
};
