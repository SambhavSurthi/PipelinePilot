"""Streamlit entry point for PipelinePilot."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import streamlit as st

from agent.graph import build_graph

from ui.components.chat import render_chat_messages
from ui.components.hitl_card import render_hitl_card
from ui.components.settings_sidebar import render_settings_sidebar


def main() -> None:
    """CLI entry: launch Streamlit with this file."""
    app_py = Path(__file__).resolve()
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_py)])


def _graph_config() -> dict:
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def _append_assistant_line(text: str, *, kind: str = "status") -> None:
    msgs = st.session_state.messages
    if msgs and msgs[-1].get("role") == "assistant" and msgs[-1].get("content") == text:
        return
    msgs.append({"role": "assistant", "content": text, "kind": kind})


def _sync_state_from_checkpoint(graph) -> None:
    snap = graph.get_state(_graph_config())
    if snap and snap.values:
        st.session_state.graph_state = dict(snap.values)


def _should_await_hitl(values: dict | None) -> bool:
    if not values:
        return False
    if values.get("error") or values.get("pr_url"):
        return False
    return bool(
        values.get("proposed_patch")
        and values.get("current_step") == "patch_ready"
    )


def _step_message(event: dict) -> str | None:
    step = event.get("current_step")
    if step == "logs_fetched":
        n = len((event.get("raw_logs") or "").splitlines())
        rid = event.get("failed_run_id")
        return f"✅ Found failed run #{rid}. Analyzing {n} log lines..."
    if step == "rca_complete":
        rc = event.get("root_cause") or ""
        snippet = rc[:100] + ("…" if len(rc) > 100 else "")
        return f"🔍 Root cause identified: {snippet}"
    if step == "context_retrieved":
        return "📚 Retrieved repository context. Generating fix..."
    if step == "patch_ready":
        return "📝 Fix generated. Please review below."
    if step == "awaiting_approval":
        return "⏸️ Waiting for your approval…"
    if step == "fix_applied":
        pr = event.get("pr_url") or "(no PR URL)"
        return f"✅ Fix pushed! PR created: {pr}"
    if step == "error" and event.get("error"):
        return f"❌ {event.get('error')}"
    return None


def _stream_graph(graph, payload: dict | None, *, resume: bool = False) -> None:
    config = _graph_config()
    stream_iter = graph.stream(
        payload,
        config=config,
        stream_mode="values",
    )
    last_event: dict | None = None
    try:
        for event in stream_iter:
            last_event = event
            st.session_state.graph_state = event
            step = event.get("current_step")
            msg = _step_message(event)
            if msg:
                _append_assistant_line(msg, kind="status")

            if resume and step == "awaiting_approval":
                continue

            if step == "awaiting_approval":
                st.session_state.awaiting_hitl = True
                break

            if step == "error":
                break

        _sync_state_from_checkpoint(graph)

        if not resume and _should_await_hitl(st.session_state.graph_state):
            st.session_state.awaiting_hitl = True
            _append_assistant_line(
                "📝 Fix generated. Please review below.", kind="status"
            )

    except Exception as e:
        st.error(f"Graph run failed: {e}")


def _render_status_badge() -> None:
    gs = st.session_state.graph_state or {}
    step = gs.get("current_step") or "idle"
    if gs.get("error") or step == "error":
        cls = "status-error"
    elif step in ("fix_applied", "END", "idle"):
        cls = "status-done"
    else:
        cls = "status-running"
    st.markdown(
        f'<p><span class="status-badge {cls}">Step: {step}</span></p>',
        unsafe_allow_html=True,
    )


def run_streamlit_dashboard() -> None:
    st.set_page_config(
        page_title="PipelinePilot",
        page_icon="🚀",
        layout="wide",
    )

    st.markdown(
        """
<style>
.status-badge { padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 500; }
.status-running { background: #FEF3C7; color: #92400E; }
.status-done { background: #D1FAE5; color: #065F46; }
.status-error { background: #FEE2E2; color: #991B1B; }
.stChatMessage { border-radius: 12px; }
</style>
""",
        unsafe_allow_html=True,
    )

    if "graph_state" not in st.session_state:
        st.session_state.graph_state = None
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "awaiting_hitl" not in st.session_state:
        st.session_state.awaiting_hitl = False
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph()

    settings = render_settings_sidebar()

    st.title("🚀 PipelinePilot")
    st.caption("Autonomous CI/CD failure triage and fix proposals")

    _render_status_badge()

    st.divider()
    render_chat_messages(st.session_state.messages)

    if st.session_state.awaiting_hitl and st.session_state.graph_state:
        st.divider()
        decision = render_hitl_card(st.session_state.graph_state)
        graph = st.session_state.graph
        cfg = _graph_config()

        if decision == "approve":
            try:
                graph.update_state(cfg, {"user_decision": "approve"})
            except Exception as e:
                st.error(f"Failed to record approval: {e}")
            else:
                st.session_state.awaiting_hitl = False
                with st.spinner("Applying approved fix..."):
                    _stream_graph(graph, None, resume=True)
                st.rerun()

        elif decision == "reject":
            fb = st.session_state.pop("hitl_pending_feedback", "") or ""
            vals = st.session_state.graph_state or {}
            try:
                graph.update_state(
                    cfg,
                    {
                        "user_decision": "reject",
                        "user_feedback": fb,
                        "rejection_count": int(vals.get("rejection_count", 0)) + 1,
                    },
                )
            except Exception as e:
                st.error(f"Failed to record rejection: {e}")
            else:
                st.session_state.awaiting_hitl = False
                with st.spinner("Re-running analysis with your feedback..."):
                    _stream_graph(graph, None, resume=True)
                st.rerun()

    prompt = st.chat_input("Describe the CI/CD issue or just say 'fix my latest failure'")

    if prompt:
        if not settings["openai_api_key"].strip() or not settings["github_pat"].strip():
            st.error("Add your OpenAI API key and GitHub PAT in the sidebar.")
        elif not settings["connected"]:
            st.error("Connect and index a repository before chatting.")
        else:
            st.session_state.messages.append(
                {"role": "user", "content": prompt, "kind": "chat"}
            )
            st.session_state.thread_id = (
                f"{settings['repo'].replace('/', '-')}-{int(time.time() * 1000)}"
            )
            st.session_state.awaiting_hitl = False

            initial_state = {
                "user_message": prompt,
                "github_pat": settings["github_pat"].strip(),
                "repo": settings["repo"],
                "model_name": settings["model_name"],
                "openai_api_key": settings["openai_api_key"].strip(),
                "rejection_count": 0,
                "max_retries": settings["max_retries"],
                "messages": [],
            }

            with st.spinner("Running agent..."):
                try:
                    _stream_graph(st.session_state.graph, initial_state, resume=False)
                except Exception as e:
                    st.error(f"Agent failed: {e}")

            st.rerun()


if __name__ == "__main__":
    run_streamlit_dashboard()
