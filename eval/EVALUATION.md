# Evaluation

Working notes for the hackathon's evaluation deliverable. Replace each `TODO` with your results.

## Testing methodology

| Layer | How | Status |
|---|---|---|
| Unit | `uv run pytest tests/ -v` uses canned CKAN responses and a real MCP client | TODO: record result |
| End to end | `scripts/smoke_test.py` runs the handshake, tool list, and a live search | TODO: record local and hosted results |
| Agent | Ask an LLM the questions below using only these tools (see the `mcp-eval` skill) | TODO |

## Agent questions

Answer these by hand from the portal first, so that each has a known answer.

1. Which department publishes the most datasets?
2. What columns does the most recent Payroll table have, and how many rows?
3. How many datasets include council district data?
4. Which budget year is the newest on the portal?
5. Ask for data the portal doesn't hold. The agent should say so and not invent an answer.

## Performance

TODO: record response times for search and query, hosted, over 10 calls. Include the first
call after the app has been idle.

## Security considerations

- Public data only, with read-only CKAN actions and no SQL endpoint.
- Fixed upstream origin, no redirects, and a 5 MB response limit.
- Identifiers are validated before any request. Errors are sanitized.
- No authentication on the endpoint. Hosting platforms' rate limits are the only throttle.

## Lessons learned

TODO
