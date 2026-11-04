# Host on Streamlit

`streamlit_app.py` serves the page at `/`, MCP at `/api/mcp`, and a health check at
`/api/health`, all from one process. It uses `st.App`, available in Streamlit 1.66.

## Before you deploy

Run the local check in the [README](../../README.md#run-it-on-your-computer). All three
smoke test lines should say `PASS`.

## Option 1: Streamlit Community Cloud (try this first)

It is free and takes minutes, but **MCP may not work there**. Community Cloud puts its own
sign-in redirect and sleep screen in front of apps. Those are made for browsers, and an MCP
client can't click through them. Only a real test will tell.

1. Push this repo to GitHub.
2. At <https://share.streamlit.io>, create an app from the repo with main file `streamlit_app.py`.
3. Under advanced settings, choose Python 3.11.
4. Make the app public, and open it to confirm the page loads.
5. Run the test against the hosted address:

   ```bash
   uv run python scripts/smoke_test.py https://YOUR-APP.streamlit.app/api/mcp
   ```

| Result | What to do |
|---|---|
| All `PASS` | Run it again after the app has been idle for a day. If it still passes, you're done. |
| Handshake `FAIL` | Community Cloud is blocking MCP. Keep the app as your public page and use Option 2 for MCP. |
| Handshake and tools `PASS`, search `FAIL` | The host is fine, but the portal is refusing that host's requests. Ask the portal's administrator about allowing them. |

## Option 2: Any container host

This runs the same code without Community Cloud's front door, using `Dockerfile.streamlit`.
Point a host that builds from a GitHub repo (Render or Google Cloud Run, for example, or
IBM Code Engine from the hackathon sandbox) at that file. It listens on `PORT`, and the
health check path is `/api/health`. Then run the smoke test against
`https://YOUR-HOST/api/mcp`.

Avoid a free tier that shuts down when idle if you need fast responses during the demo.

## Turn on the chat agent

In the app's secrets settings, add:

```toml
ANTHROPIC_API_KEY = "your-key"
APP_PASSWORD = "a-long-password-you-choose"
```

Set a spending limit for the key in the Claude Console. The per-session question limit
resets on refresh, so the password and spending limit are what actually control cost.
The agent runs its tools inside the app, so it doesn't need `/api/mcp` to be reachable.

## Connect a client

Add the `/api/mcp` address as a remote MCP server. In Claude, that means a
[custom connector](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Before making it public

The GSA hackathon page says prototypes are not deployed publicly and work happens in sandbox
environments. Confirm with the organizers at office hours, and with HITS, that a public
endpoint is acceptable. Keep the "not an official City service" label in place.
