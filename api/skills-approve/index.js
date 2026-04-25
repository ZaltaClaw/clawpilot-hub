const GH_REPO = process.env.GITHUB_REPO || "ZaltaClaw/clawpilot-hub";
const GH_TOKEN = process.env.GITHUB_TOKEN || "";

function getUser(req) {
  const header = req.headers["x-ms-client-principal"];
  if (!header) return null;
  try { return JSON.parse(Buffer.from(header, "base64").toString("utf8")); }
  catch (e) { return null; }
}
function isAdmin(user) { return user && Array.isArray(user.userRoles) && user.userRoles.includes("admin"); }

async function ghRequest(path, opts = {}) {
  if (!GH_TOKEN) throw new Error("GITHUB_TOKEN not configured");
  const res = await fetch(`https://api.github.com${path}`, {
    ...opts,
    headers: {
      "Authorization": `Bearer ${GH_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      ...(opts.headers || {})
    }
  });
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = text; }
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${typeof body === "object" ? body.message : body}`);
  return body;
}

module.exports = async function (context, req) {
  const user = getUser(req);
  if (!isAdmin(user)) { context.res = { status: 403, body: { error: "admin only" } }; return; }

  const { issueNumber, action, comment } = req.body || {};
  if (!issueNumber || !["approve", "reject"].includes(action)) {
    context.res = { status: 400, body: { error: "issueNumber + action(approve|reject) required" } };
    return;
  }

  try {
    const commentBody = action === "approve"
      ? `✅ Approved by ${user.userDetails}.${comment ? `\n\n${comment}` : ""}\n\nMerging into the next \`data/skills.json\` build.`
      : `❌ Rejected by ${user.userDetails}.${comment ? `\n\nReason: ${comment}` : ""}`;
    await ghRequest(`/repos/${GH_REPO}/issues/${issueNumber}/comments`, {
      method: "POST",
      body: JSON.stringify({ body: commentBody })
    });
    await ghRequest(`/repos/${GH_REPO}/issues/${issueNumber}/labels`, {
      method: "PUT",
      body: JSON.stringify({ labels: ["skill-submission", action === "approve" ? "approved" : "rejected"] })
    });
    await ghRequest(`/repos/${GH_REPO}/issues/${issueNumber}`, {
      method: "PATCH",
      body: JSON.stringify({ state: "closed", state_reason: action === "approve" ? "completed" : "not_planned" })
    });
    context.res = { status: 200, body: { ok: true, action } };
  } catch (e) {
    context.log.error("approve failed:", e.message);
    context.res = { status: 500, body: { error: e.message } };
  }
};
