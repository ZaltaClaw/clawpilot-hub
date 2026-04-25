const GH_REPO = process.env.GITHUB_REPO || "ZaltaClaw/clawpilot-hub";
const GH_TOKEN = process.env.GITHUB_TOKEN || "";

function getUser(req) {
  const header = req.headers["x-ms-client-principal"];
  if (!header) return null;
  try { return JSON.parse(Buffer.from(header, "base64").toString("utf8")); }
  catch (e) { return null; }
}
function isAdmin(user) { return user && Array.isArray(user.userRoles) && user.userRoles.includes("admin"); }

async function ghRequest(path) {
  if (!GH_TOKEN) throw new Error("GITHUB_TOKEN not configured");
  const res = await fetch(`https://api.github.com${path}`, {
    headers: {
      "Authorization": `Bearer ${GH_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28"
    }
  });
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = text; }
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${typeof body === "object" ? body.message : body}`);
  return body;
}

module.exports = async function (context, req) {
  const user = getUser(req);
  const includePending = isAdmin(user) && (req.query.include === "pending");
  const result = { approved: [], pending: [] };
  try {
    if (includePending) {
      const issues = await ghRequest(`/repos/${GH_REPO}/issues?state=open&labels=skill-submission,pending-review&per_page=50`);
      result.pending = issues.map(i => ({
        number: i.number,
        title: i.title,
        url: i.html_url,
        submitter: ((i.body || "").match(/\*\*Submitted by:\*\*\s+(\S+)/) || [])[1] || "unknown",
        createdAt: i.created_at
      }));
    }
    context.res = { status: 200, body: result };
  } catch (e) {
    context.log.error("list failed:", e.message);
    context.res = { status: 500, body: { error: e.message } };
  }
};
