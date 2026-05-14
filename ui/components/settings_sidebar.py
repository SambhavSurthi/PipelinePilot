"""Streamlit sidebar: API keys, repo connect/index, and agent settings."""

from __future__ import annotations

import streamlit as st

from rag.indexer import index_repository

MODEL_PRESETS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]


def render_settings_sidebar() -> dict:
    """Return user settings for the main app."""
    st.sidebar.markdown("### PipelinePilot")

    if "openai_api_key" not in st.session_state:
        st.session_state.openai_api_key = ""
    if "github_pat" not in st.session_state:
        st.session_state.github_pat = ""
    if "repo_input" not in st.session_state:
        st.session_state.repo_input = ""
    if "repo_connected" not in st.session_state:
        st.session_state.repo_connected = False
    if "connected_repo" not in st.session_state:
        st.session_state.connected_repo = ""
    if "repo_stats" not in st.session_state:
        st.session_state.repo_stats = None
    if "connect_error" not in st.session_state:
        st.session_state.connect_error = None

    # --- 1) API Keys (always visible) ---
    st.sidebar.header("🔑 API Keys")

    openai_api_key = st.sidebar.text_input(
        "OpenAI API Key",
        value=st.session_state.openai_api_key,
        type="password",
        help="Stored only in this browser session (session_state).",
    )
    github_pat = st.sidebar.text_input(
        "GitHub Personal Access Token",
        value=st.session_state.github_pat,
        type="password",
        help="Stored only in this browser session (session_state).",
    )
    st.session_state.openai_api_key = openai_api_key
    st.session_state.github_pat = github_pat

    preset = st.sidebar.selectbox(
        "Model",
        options=MODEL_PRESETS + ["Custom…"],
        index=0,
    )
    if preset == "Custom…":
        if "custom_model_name" not in st.session_state:
            st.session_state.custom_model_name = "gpt-4o"
        model_name = st.sidebar.text_input(
            "Custom model name",
            value=st.session_state.custom_model_name,
        )
        st.session_state.custom_model_name = model_name
    else:
        model_name = preset

    keys_ok = bool(openai_api_key.strip()) and bool(github_pat.strip())
    repo = (st.session_state.repo_input or "").strip()

    # --- 2) Repository (visible once keys are present) ---
    if keys_ok:
        st.sidebar.header("📦 Repository")
        repo_raw = st.sidebar.text_input(
            "GitHub Repo",
            value=st.session_state.repo_input,
            placeholder="owner/repo",
            help='Format: owner/repo (e.g. "torvalds/linux").',
        )
        st.session_state.repo_input = repo_raw
        repo = (repo_raw or "").strip()

        st.sidebar.header("⚙️ Settings")
        max_retries = st.sidebar.slider(
            "Max retries before giving up",
            min_value=1,
            max_value=5,
            value=3,
        )
        auto_index = st.sidebar.checkbox("Auto-index on connect", value=True)

        if st.sidebar.button("🔗 Connect & Index Repo", use_container_width=True):
            st.session_state.connect_error = None
            st.session_state.repo_stats = None
            st.session_state.repo_connected = False
            st.session_state.connected_repo = ""

            if not repo or "/" not in repo or repo.count("/") != 1:
                st.session_state.connect_error = "Enter a repository as owner/repo."
            else:
                with st.sidebar.spinner("Indexing repository..."):
                    result = index_repository(
                        github_pat.strip(),
                        repo,
                        auto_index=auto_index,
                    )
                if result.get("ok"):
                    st.session_state.repo_connected = True
                    st.session_state.connected_repo = repo
                    st.session_state.repo_stats = {
                        "file_count": result.get("file_count", 0),
                        "workflow_count": result.get("workflow_count", 0),
                        "last_failed_run": result.get("last_failed_run"),
                        "indexed": result.get("indexed", False),
                    }
                else:
                    st.session_state.connect_error = result.get("error") or "Connection failed."

        if st.session_state.repo_connected and st.session_state.repo_stats:
            st.sidebar.success("✅ Repository connected")
            stats = st.session_state.repo_stats
            st.sidebar.metric("File count (indexed extensions)", stats.get("file_count", 0))
            st.sidebar.metric("Workflow file count", stats.get("workflow_count", 0))
            lf = stats.get("last_failed_run")
            if lf:
                msg = (
                    f"Last failed run #{lf.get('id')} — {lf.get('name', '')}\n\n"
                    f"{lf.get('created_at', '')}\n\n"
                    f"{lf.get('html_url', '')}"
                )
                st.sidebar.caption(msg)
            else:
                st.sidebar.caption("No failed workflow runs returned for this repo.")

        if st.session_state.connect_error:
            st.sidebar.error(st.session_state.connect_error)

    else:
        st.sidebar.info("Enter API keys to unlock repository setup.")
        st.sidebar.header("⚙️ Settings")
        max_retries = st.sidebar.slider(
            "Max retries before giving up",
            min_value=1,
            max_value=5,
            value=3,
        )
        auto_index = st.sidebar.checkbox("Auto-index on connect", value=True)

    connected = (
        keys_ok
        and st.session_state.repo_connected
        and repo
        and repo == (st.session_state.connected_repo or "").strip()
    )

    return {
        "openai_api_key": openai_api_key,
        "github_pat": github_pat,
        "repo": repo,
        "model_name": (model_name or "").strip(),
        "connected": connected,
        "max_retries": max_retries,
        "auto_index": auto_index,
    }
