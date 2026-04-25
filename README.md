# ClawPilot Hub

The AI agent skills directory for **Microsoft MCAPS Israel** — curated, security-vetted skills built for [ClawPilot](https://clawpilot.ai), also compatible with Claude Code, Cursor & GitHub Copilot.

🌐 **Live:** [hidden-orbit-fd6v.here.now](https://hidden-orbit-fd6v.here.now/) (preview) · Azure SWA URL coming soon
🦞 Built by [ZaltaClaw](https://github.com/ZaltaClaw) for Microsoft Israel

## What it is

A static directory site (think `agentskills.co.il` but Microsoft-branded, Hebrew-ready, MCAPS-focused) where:

- Anyone can browse curated AI skills
- Microsoft employees (and any AAD account) can sign in with Microsoft and submit their own SKILL.md
- Submissions land as GitHub issues for review
- Roey (admin role) approves/rejects from a dedicated `/admin/` console
- Approved skills get merged into `data/skills.json` and auto-redeployed

## Stack

- **Hosting:** Azure Static Web Apps (free tier)
- **Auth:** Microsoft Entra (`/.auth/login/aad`) — zero-config via SWA
- **API:** Azure Functions (Node 18, v4 programming model)
- **Submission queue:** GitHub Issues (label: `skill-submission`)
- **Frontend:** vanilla HTML/CSS/JS, Microsoft Fluent design language
- **Logo:** ClawPilot brand mark
- **Submission flow:** SWA AAD auth → Function calls GitHub API → opens issue → admin reviews

## Architecture

```
Browser ──(MS login)──▶ SWA easy-auth ──▶ injects principal header
   │
   ├─ POST /api/skills-submit (auth required)  ──▶ GitHub issue
   ├─ GET  /api/skills-list?include=pending  (admin only) ──▶ pending issues
   └─ POST /api/skills-approve (admin only)   ──▶ comment + close issue
```

## Local dev

```bash
# Frontend only:
python3 -m http.server 8765

# Full stack (with API + auth emulation):
npm i -g @azure/static-web-apps-cli
swa start . --api-location api
```

## Configuration

Required SWA app settings:

- `AAD_CLIENT_ID` — Microsoft Entra app client ID
- `AAD_CLIENT_SECRET` — Microsoft Entra client secret
- `GITHUB_TOKEN` — fine-grained PAT scoped to issues:write on this repo
- `GITHUB_REPO` — defaults to `ZaltaClaw/clawpilot-hub`

Admin role assigned to Roey via the Azure Portal (Static Web App → Role management).

## License

MIT
