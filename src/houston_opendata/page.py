"""Streamlit page: how to connect, what the server offers, and a live test."""

from __future__ import annotations

import asyncio
import hmac
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from houston_opendata import agent, portal  # noqa: E402
from houston_opendata.config import settings  # noqa: E402

MAX_QUESTIONS = 10
HISTORY_MESSAGES = 7  # Odd, so the window always starts with a question.
EXAMPLES = "Try: Which datasets cover council districts?"
PLUS_EXAMPLES = "Try: I just moved to 901 Bagby St. Who represents me?"

TOOLS = [
    ("houston_search_datasets", "Search the catalog by keyword, department, or topic"),
    ("houston_get_dataset", "Open a dataset and list its resources"),
    ("houston_describe_table", "List a table's columns and row count"),
    ("houston_query_records", "Read rows with filters, sorting, and paging"),
    ("houston_list_organizations", "List departments and their dataset counts"),
    ("houston_list_groups", "List topic groups and their dataset counts"),
]
PLUS_TOOLS = [
    (
        "houston_lookup_address",
        "Find an address's city limits, council district, and super neighborhood",
    ),
]


@st.cache_data(ttl=300, show_spinner="Searching the portal…")
def search(query: str) -> dict:
    return asyncio.run(portal.search_datasets(query, limit=10))


@st.cache_data(ttl=300, show_spinner="Opening the dataset…")
def dataset(name: str) -> dict:
    return asyncio.run(portal.get_dataset(name))


@st.cache_data(ttl=300, show_spinner="Reading rows…")
def records(resource_id: str) -> dict:
    return asyncio.run(portal.query_records(resource_id, limit=10))


def endpoint_url() -> str:
    base = (st.context.url or "").split("?")[0].rstrip("/")
    return f"{base}/api/mcp" if base else "/api/mcp"


def secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, ""))
    except FileNotFoundError:
        return ""
    except Exception:  # noqa: BLE001 - treat unreadable secrets as not configured
        return ""


def arcgis_on() -> bool:
    """Ask Houston+ when USE_ARCGIS is true in the secrets or the environment."""
    from_env = getattr(settings, "use_arcgis", False)  # safe if config is stale
    return from_env or secret("USE_ARCGIS").strip().lower() == "true"


def unlocked(password: str) -> bool:
    if st.session_state.get("unlocked"):
        return True
    entered = st.text_input("Password", type="password")
    if entered and hmac.compare_digest(entered, password):
        st.session_state["unlocked"] = True
        return True
    if entered:
        st.error("That password isn't right.")
    return False


def show_message(role: str, content: str) -> None:
    # A bare $ would otherwise start a math formula in Streamlit Markdown.
    st.chat_message(role).markdown(content.replace("$", "\\$"))


def render_chat() -> None:
    api_key, password = secret("ANTHROPIC_API_KEY"), secret("APP_PASSWORD")
    if not api_key or not password:
        st.info("The chat isn't set up yet. Add ANTHROPIC_API_KEY and APP_PASSWORD.")
        return
    if not unlocked(password):
        return

    history = st.session_state.setdefault("history", [])
    for message in history:
        show_message(message["role"], message["content"])

    asked = sum(1 for message in history if message["role"] == "user")
    if asked >= MAX_QUESTIONS:
        st.info("You've reached the limit of questions for this session.")
        return

    question = st.chat_input("Ask about Houston open data")
    if not history and not question:
        st.caption(PLUS_EXAMPLES if USE_ARCGIS else EXAMPLES)
    if not question:
        return

    history.append({"role": "user", "content": question})
    show_message("user", question)
    try:
        with st.spinner("Checking the portal…"):
            answer = agent.ask(
                agent.make_client(api_key),
                history[-HISTORY_MESSAGES:],
                use_arcgis=USE_ARCGIS,
            )
    except Exception as exc:  # noqa: BLE001 - show a safe message, never the key
        history.pop()
        st.error(f"The assistant couldn't answer ({type(exc).__name__}). Try again.")
        return
    history.append({"role": "assistant", "content": answer})
    show_message("assistant", answer)


USE_ARCGIS = arcgis_on()
APP_NAME = "Ask Houston+" if USE_ARCGIS else "Ask Houston"
SOURCES = "Open Data Portal + City GIS" if USE_ARCGIS else "Open Data Portal"

st.set_page_config(page_title=APP_NAME, layout="centered")

st.title(APP_NAME)
st.caption(f"Houston Open Data MCP · {SOURCES}")
st.write(
    "Lets an AI assistant search and read public data from the "
    f"[City of Houston Open Data portal]({settings.portal_url})"
    + (" and City GIS data sources" if USE_ARCGIS else "")
    + ". It only reads data, and it needs no sign-in."
)
st.caption("Hackathon prototype. Not an official City of Houston service.")

ask, connect, try_it = st.tabs(["Ask", "Connect", "Try it"])

with ask:
    render_chat()

with connect:
    st.subheader("Server address")
    st.code(endpoint_url(), language=None)
    st.write("Add this address as a remote MCP server in your AI client.")
    st.subheader("Tools")
    st.dataframe(
        # The MCP endpoint registers its tools at startup from the environment.
        pd.DataFrame(
            TOOLS + (PLUS_TOOLS if getattr(settings, "use_arcgis", False) else []),
            columns=["Tool", "What it does"],
        ),
        hide_index=True,
        width="stretch",
    )

with try_it:
    st.write("These results come from the same code the MCP tools run.")
    with st.form("search"):
        query = st.text_input("Search the catalog", placeholder="council district")
        submitted = st.form_submit_button("Search")

    if submitted:
        st.session_state["query"] = query

    if "query" in st.session_state:
        try:
            found = search(st.session_state["query"])
        except portal.PortalError as exc:
            st.error(f"{exc.error} {exc.hint}")
            st.stop()

        st.write(f"{found['total']:,} datasets found. Showing up to 10.")
        if not found["datasets"]:
            st.stop()

        titles = {d["title"]: d["name"] for d in found["datasets"]}
        title = st.selectbox("Dataset", list(titles))
        try:
            detail = dataset(titles[title])
        except portal.PortalError as exc:
            st.error(f"{exc.error} {exc.hint}")
            st.stop()

        st.markdown(f"[Open on the portal]({detail['portal_url']})")
        queryable = {
            r["name"] or r["id"]: r["id"] for r in detail["resources"] if r["queryable"]
        }
        if not queryable:
            st.info("This dataset has no table that can be read row by row.")
        else:
            resource = st.selectbox("Table", list(queryable))
            try:
                rows = records(queryable[resource])
            except portal.PortalError as exc:
                st.error(f"{exc.error} {exc.hint}")
                st.stop()
            st.write(f"First rows of {rows['total']:,}.")
            st.dataframe(pd.DataFrame(rows["records"]), hide_index=True)
