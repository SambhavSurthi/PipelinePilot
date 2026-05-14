"""Chat message rendering for the main conversation area."""

from __future__ import annotations

import streamlit as st


def render_chat_messages(messages: list) -> None:
    """Render stored chat/status messages."""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        kind = msg.get("kind", "chat")

        if role == "user":
            with st.chat_message("user"):
                st.write(content)
            continue

        if role == "assistant" and kind == "status":
            with st.chat_message("assistant", avatar="🤖"):
                st.info(content)
            continue

        if role == "assistant" and kind == "system":
            with st.chat_message("assistant", avatar="🤖"):
                with st.status("System", state="complete"):
                    st.write(content)
            continue

        if role == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.write(content)
