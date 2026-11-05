# Security

This is a hackathon prototype from a City of Houston employee, built from the GSA MCP
hackathon template. It isn't GSA software or an official City of Houston service.

To report a security problem, please contact the repository owner through GitHub. Don't
include sensitive details in a public issue.

## Security design

- **Data:** the server reads public data from the City of Houston Open Data portal. It has
  no write actions and no SQL endpoint.
- **Requests:** the portal address is set in server configuration, never by a tool argument.
  Redirects are disabled, responses are limited to 5 MB, and upstream errors are sanitized.
- **Inputs:** dataset, organization, group, and resource identifiers are validated before
  any request is sent.
- **Portal content:** the chat agent treats everything the tools return as data, not as
  instructions. This reduces the risk of prompt injection but doesn't eliminate it.
- **Secrets:** the API key and app password belong in Streamlit secrets or a local file that
  Git ignores. They must never be committed.

## Known limits

- The MCP endpoint has no authentication, which is why it's limited to public data. Don't
  add private data without adding authentication and access controls.
- The chat page is protected by one shared password. Its per-session question limit resets
  on refresh, so the API spending limit is the real cost control.
- The server has no rate limiting of its own.
