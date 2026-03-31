# iCloud Email HTTPS MCP

`icloud-email-https-mcp` is a read-only [FastMCP](https://gofastmcp.com/) server for iCloud Mail over IMAP.

It is designed for Notion Custom Agents and similar MCP clients. The server can:

- verify the mailbox connection
- list mailboxes such as `INBOX` and `Sent Messages`
- search recent mail without changing read state
- fetch full message bodies by IMAP UID

It is intentionally read-only:

- mailboxes are opened with `readonly=True`
- messages are fetched with `BODY.PEEK[]`
- there are no send, delete, move, or flag-changing tools

## Recommended Setup

The recommended default is:

1. publish this repo to GitHub
2. turn the Railway service into a reusable template
3. let users deploy their own copy on Railway
4. let users open the deployed app's setup page
5. let users paste the generated MCP URL and bearer token into Notion

This avoids local tunnels and gives each user their own deployment and their own iCloud credentials.

## End-User Flow

The intended self-serve flow is:

1. click your Railway template
2. enter `EMAIL_IMAP_USERNAME` and `EMAIL_IMAP_PASSWORD`
3. let Railway generate `EMAIL_MCP_AUTH_TOKEN`
4. open the deployed service root, for example `https://your-service.up.railway.app`
5. copy the Notion MCP URL from the setup page
6. copy `EMAIL_MCP_AUTH_TOKEN` from Railway Variables
7. paste both into a Notion Custom Agent

The setup page is intentionally public-safe:

- it shows the exact `https://.../mcp` URL
- it links to Apple's app-specific password instructions
- it reminds the user where to copy the token from
- it does not print the bearer token value publicly

## Quickstart

### 1. Install dependencies

```bash
uv sync
```

### 2. Create `.env`

Interactive:

```bash
uv run email-mcp init
```

Non-interactive:

```bash
uv run email-mcp init \
  --email yourname@icloud.com \
  --app-password your-app-specific-password
```

This writes `.env` with:

- `EMAIL_IMAP_HOST=imap.mail.me.com`
- `EMAIL_IMAP_PORT=993`
- `EMAIL_IMAP_USERNAME=...`
- `EMAIL_IMAP_PASSWORD=...`
- `EMAIL_IMAP_USE_SSL=true`
- `EMAIL_DEFAULT_MAILBOX=INBOX`
- `EMAIL_MCP_AUTH_TOKEN=<generated random token>`

You can also start from `.env.example`.

### 3. Test locally

Stdio mode:

```bash
uv run email-mcp
```

HTTP mode:

```bash
uv run email-mcp --transport http --host 127.0.0.1 --port 8000
```

Endpoints:

- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`
- Setup page: `http://127.0.0.1:8000/`

## Railway Deployment

Railway is the recommended default because it supports Dockerfile-based deploys, automatic HTTPS, and simple environment variable setup.

### 1. Install and log into Railway

```bash
brew install railway
railway login
```

### 2. Create or link a Railway project

From the repo root:

```bash
railway init
```

### 3. Deploy

```bash
railway up
```

This repo includes:

- `Dockerfile`
- `railway.json`

Railway will build from the Dockerfile and run the service on its injected `PORT`.

### 4. Set service variables

If Railway did not import them from your local `.env`, set these in the Railway dashboard:

- `EMAIL_IMAP_HOST=imap.mail.me.com`
- `EMAIL_IMAP_PORT=993`
- `EMAIL_IMAP_USERNAME=yourname@icloud.com`
- `EMAIL_IMAP_PASSWORD=your-app-specific-password`
- `EMAIL_IMAP_USE_SSL=true`
- `EMAIL_DEFAULT_MAILBOX=INBOX`
- `EMAIL_MCP_AUTH_TOKEN=<your generated token>`

### 5. Get the public URL

Once deployed, Railway gives you a public HTTPS hostname, for example:

```text
https://email-mcp-production.up.railway.app
```

Open the hostname in a browser. The setup page shows:

- the exact Notion MCP URL
- the header name
- the Apple app-specific password help link
- the remaining steps for copying the token from Railway Variables

If you still want the CLI output, print the Notion values with:

```bash
uv run email-mcp notion --base-url https://email-mcp-production.up.railway.app
```

That prints:

- Notion MCP URL: `https://email-mcp-production.up.railway.app/mcp`
- Header name: `Authorization`
- Header value: `Bearer <your token>`

## Railway Template

For the cleanest GitHub-to-Notion onboarding, publish this service as a Railway template.

Recommended template inputs:

- required: `EMAIL_IMAP_USERNAME`
- required: `EMAIL_IMAP_PASSWORD`
- generated secret: `EMAIL_MCP_AUTH_TOKEN`

Recommended fixed defaults:

- `EMAIL_IMAP_HOST=imap.mail.me.com`
- `EMAIL_IMAP_PORT=993`
- `EMAIL_IMAP_USE_SSL=true`
- `EMAIL_DEFAULT_MAILBOX=INBOX`

After a user deploys the template, they should:

1. open the generated Railway URL in a browser
2. copy the `MCP server URL` shown on the setup page
3. copy `EMAIL_MCP_AUTH_TOKEN` from Railway Variables
4. paste both into Notion

## Notion Setup

In Notion Custom Agent:

1. `Settings`
2. `Tools & Access`
3. `Add connection`
4. `Custom MCP server`

Then enter:

- URL: `https://your-railway-hostname/mcp`
- Authentication: header-based or bearer token
- Header name: `Authorization`
- Header value: `Bearer <your EMAIL_MCP_AUTH_TOKEN>`

Notion requires a publicly reachable `https://...` URL, which is why local-only deployment is not enough for production use.

## CLI Helpers

Generate a token:

```bash
uv run email-mcp token
```

Create `.env` interactively:

```bash
uv run email-mcp init
```

Print the Notion URL and header:

```bash
uv run email-mcp notion --base-url https://your-service.up.railway.app
```

Show CLI help:

```bash
uv run email-mcp --help
```

## iCloud Notes

Use an Apple app-specific password, not your normal Apple account password.

Typical iCloud IMAP settings:

- host: `imap.mail.me.com`
- port: `993`
- SSL: `true`

## Tool Surface

The MCP server exposes:

- `connection_status`
- `list_mailboxes`
- `list_messages`
- `get_message`

`list_messages` supports:

- `mailbox`
- `unread_only`
- `limit`
- `offset`
- `since_days`
- `sender`
- `subject`

`get_message` expects the `uid` returned by `list_messages`.

## Other Hosting Options

Railway is the recommended default, but the same Docker image should also work on other container-friendly hosts such as Render, Fly.io, or a small VPS.

For development or short-lived testing, a local server plus Cloudflare Tunnel is fine. It is not the recommended long-term path.

Vercel is not recommended for this project because Vercel is a function platform, not a Docker container host, and this server is a better fit for a long-running HTTP deployment.

## Security

- Do not commit `.env`
- Do not share your iCloud app-specific password
- Keep bearer-token auth enabled on public deployments
- Revoke any app-specific password that was ever exposed in logs, screenshots, or commit history

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests
```
