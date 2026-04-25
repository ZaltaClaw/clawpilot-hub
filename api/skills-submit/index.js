const GH_REPO = process.env.GITHUB_REPO || "ZaltaClaw/clawpilot-hub";
const GH_TOKEN = process.env.GITHUB_TOKEN || "";

function getUser(req) {
  const header = req.headers["x-ms-client-principal"];
  if (!header) return null;
  try { return JSON.parse(Buffer.from(header, "base64").toString("utf8")); }
  catch (e) { return null; }
}

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
  if (!user) { context.res = { status: 401, body: { error: "auth required" } }; return; }

  const p = req.body || {};
  const { name, description, category, version, author, tags, compatible, skillMd } = p;
  if (!name || !skillMd) { context.res = { status: 400, body: { error: "name and skillMd required" } }; return; }
  if (skillMd.length > 200_000) { context.res = { status: 413, body: { error: "SKILL.md too large" } }; return; }

  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const submitter = user.userDetails || user.userId || "unknown";
  const provider = user.identityProvider || "aad";

  const issueBody = [
    "## Skill submission",
    "",
    `**Submitted by:** ${submitter} (\`${provider}\`)`,
    "",
    `- **Name:** ${name}`,
    `- **Slug:** \`${slug}\``,
    `- **Category:** ${category || "Other"}`,
    `- **Version:** ${version || "1.0.0"}`,
    `- **Author:** ${author || submitter}`,
    `- **Tags:** ${(tags || []).join(", ") || "(none)"}`,
    `- **Compatible with:** ${(compatible || []).join(", ")}`,
    "",
    `### Description`,
    description || "(no description)",
    "",
    `### SKILL.md`,
    "```markdown",
    String(skillMd).slice(0, 180_000),
    "```",
    "",
    "---",
    "_Submitted via ClawPilot Hub_"
  ].join("\n");

  try {
    const issue = await ghRequest(`/repos/${GH_REPO}/issues`, {
      method: "POST",
      body: JSON.stringify({
        title: `[skill] ${name}`,
        body: issueBody,
        labels: ["skill-submission", "pending-review"]
      })
    });
    context.res = { status: 201, body: { ok: true, issueNumber: issue.number, issueUrl: issue.html_url } };
  } catch (e) {
    context.log.error("submit failed:", e.message);
    context.res = { status: 500, body: { error: e.message } };
  }
};
