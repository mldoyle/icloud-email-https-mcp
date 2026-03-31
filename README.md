# iCloud Email HTTPS MCP

`icloud-email-https-mcp` is a read-only [FastMCP](https://gofastmcp.com/) server for iCloud Mail over IMAP.

It is designed for Notion Custom Agents and similar MCP clients that require a public HTTPS MCP server. The server can:

- verify the mailbox connection
- list mailboxes such as `INBOX` and `Sent Messages`
- search recent mail without changing read state
- fetch full message bodies by IMAP UID

It is intentionally read-only:

- mailboxes are opened with `readonly=True`
- messages are fetched with `BODY.PEEK[]`
- there are no send, delete, move, or flag-changing tools

## Deploy On Railway

The fastest way to use this server is to use this Railway template:

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/szLHU-?referralCode=qW_MxP&utm_medium=integration&utm_source=template&utm_campaign=generic)

Simple setup:

1. Setup on Railway, i.e. connect a GitHub account. Click deploy.
2. Generate an Apple app-specific password for your iCloud account:
   https://support.apple.com/en-ca/102654
3. In Railway, set:
   - `EMAIL_USERNAME` to your iCloud address
   - `APP_SPECIFIC_PASSWORD` to your Apple app-specific password
4. Let Railway generate a `EMAIL_MCP_AUTH_TOKEN`.
5. Open your deployed Railway URL in a browser.
6. Copy the `MCP server URL` shown on the setup page.
7. Copy `EMAIL_MCP_AUTH_TOKEN` from Railway Variables.
8. In Notion Custom Agent, add a Custom MCP server using:
   - URL: the setup page's `MCP server URL`
   - Authentication: Bearer Token
   - Bearer Token: `Bearer <your EMAIL_MCP_AUTH_TOKEN>`

The setup page is the root of your public Railway domain, for example `https://your-service.up.railway.app/`.
It is public-safe: it shows the exact Notion connection values, but it does not expose the bearer token.

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
- `EMAIL_USERNAME=...`
- `APP_SPECIFIC_PASSWORD=...`
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
- `EMAIL_USERNAME=yourname@icloud.com`
- `APP_SPECIFIC_PASSWORD=your-app-specific-password`
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
- a suggested connection name
- `Authentication: Bearer Token`
- the bearer token format and a reminder to copy `EMAIL_MCP_AUTH_TOKEN` from Railway Variables

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

- required: `EMAIL_USERNAME`
- required: `APP_SPECIFIC_PASSWORD`
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

`EMAIL_IMAP_USERNAME` and `EMAIL_IMAP_PASSWORD` are still accepted for backward compatibility, but new setups should use `EMAIL_USERNAME` and `APP_SPECIFIC_PASSWORD`.

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
