"""The chat agent's tool loop, using a fake model and a fake portal."""

from __future__ import annotations

import json
from types import SimpleNamespace as NS

from houston_opendata import agent, portal


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.replies)


def tool_use(name, args):
    block = NS(type="tool_use", id="t1", name=name, input=args)
    return NS(stop_reason="tool_use", content=[block])


def text(value):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=value)])


def test_agent_runs_a_tool_then_answers(monkeypatch):
    async def fake_search(query, organization, group, limit, offset):
        return {"datasets": [], "total": 0, "query": query, "limit": limit}

    monkeypatch.setattr(portal, "search_datasets", fake_search)
    client = FakeClient(
        [
            tool_use("houston_search_datasets", {"query": "x", "limit": 999}),
            text("Done"),
        ]
    )
    answer = agent.ask(client, [{"role": "user", "content": "Find x"}])

    assert answer == "Done"
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "t1"
    assert json.loads(result["content"])["limit"] == agent.MAX_ROWS_PER_CALL


def test_portal_errors_go_back_to_the_model():
    output = json.loads(
        agent.run_tool("houston_describe_table", {"resource_id": "bad"})
    )
    assert "hint" in output


def test_missing_input_and_unknown_tools_do_not_crash():
    assert "error" in json.loads(agent.run_tool("houston_get_dataset", {}))
    assert "error" in json.loads(agent.run_tool("not_a_tool", {}))


def test_tool_loop_stops_at_the_limit():
    replies = [tool_use("not_a_tool", {})] * agent.MAX_TOOL_ROUNDS
    answer = agent.ask(FakeClient(replies), [{"role": "user", "content": "Loop"}])
    assert "too many lookups" in answer
