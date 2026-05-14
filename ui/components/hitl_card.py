"""Human-in-the-loop approval card for proposed patches."""

from __future__ import annotations

import streamlit as st

from agent.state import PipelineState


def render_hitl_card(state: PipelineState) -> str | None:
    st.warning("⚠️ PipelinePilot needs your approval before making changes")

    col_left, col_right = st.columns([0.6, 0.4])

    with col_left:
        st.subheader("🔍 Root Cause Analysis")
        st.info(state.get("root_cause") or "No root cause available.")

        m1, m2, m3 = st.columns(3)
        m1.metric("Fix type", state.get("fix_type") or "—")
        affected = state.get("affected_files") or []
        m2.metric("Affected files", len(affected))
        m3.metric("Confidence", (state.get("confidence") or "—").capitalize())

        failed_step = state.get("failed_step") or {}
        with st.expander("Failed Step Details"):
            st.write(f"**Job:** {failed_step.get('job_name', 'N/A')}")
            st.write(f"**Step:** {failed_step.get('step_name', 'N/A')}")
            excerpt = failed_step.get("log_excerpt") or "No log excerpt."
            st.code(excerpt, language="text")

    with col_right:
        st.subheader("📝 Proposed Fix")
        proposed_patch = state.get("proposed_patch") or {}
        if not proposed_patch:
            st.caption("No patch proposed.")
        else:
            for filename, patch_data in proposed_patch.items():
                st.subheader(filename)
                diff = (patch_data or {}).get("unified_diff") or ""
                st.code(diff, language="diff")
                st.caption((patch_data or {}).get("explanation") or "")

    st.info(state.get("patch_explanation") or "No overall explanation provided.")

    if "hitl_reject_mode" not in st.session_state:
        st.session_state.hitl_reject_mode = False

    c1, c2 = st.columns(2)
    with c1:
        approve = st.button(
            "✅ Approve & Push Fix",
            use_container_width=True,
            type="primary",
            key="hitl_approve",
        )
    with c2:
        reject_click = st.button(
            "✗ Reject — Try Again",
            use_container_width=True,
            key="hitl_reject",
        )

    if reject_click:
        st.session_state.hitl_reject_mode = True

    if approve:
        st.session_state.hitl_reject_mode = False
        return "approve"

    if st.session_state.hitl_reject_mode:
        feedback = st.text_input(
            "Tell the agent what's wrong with this fix",
            key="hitl_feedback_text",
        )
        if st.button("Submit Rejection", key="hitl_reject_submit"):
            st.session_state.hitl_reject_mode = False
            st.session_state.hitl_pending_feedback = feedback
            return "reject"

    return None
