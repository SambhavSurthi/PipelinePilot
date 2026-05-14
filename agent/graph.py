from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import PipelineState
from agent.nodes.fetch_logs import fetch_logs_node
from agent.nodes.analyze_rca import analyze_rca_node
from agent.nodes.retrieve_context import retrieve_context_node
from agent.nodes.generate_patch import generate_patch_node
from agent.nodes.hitl_approval import hitl_approval_node
from agent.nodes.apply_fix import apply_fix_node

# Import refine_patch if created, else we can reuse or define it. We created refine_patch_node.
from agent.nodes.refine_patch import refine_patch_node

def global_error_router(state: PipelineState):
    """Check for errors before routing."""
    if state.get("error"):
        return END
    return None

def router_after_rca(state: PipelineState):
    if state.get("error"):
        return END
    fix_type = state.get("fix_type")
    confidence = state.get("confidence")
    if fix_type == "unknown" or confidence == "low":
        return END
    return ["retrieve_context", "generate_patch"]

def join_context_and_patch(state: PipelineState):
    # Dummy node to wait for both parallel branches
    if state.get("error"):
        return {"current_step": "error"}
    return {"current_step": "context_retrieved"}

def router_after_hitl(state: PipelineState):
    if state.get("error"):
        return END
    decision = state.get("user_decision")
    rejection_count = state.get("rejection_count", 0)
    
    if decision == "approve":
        return "apply_fix"
    elif decision == "reject":
        cap = state.get("max_retries")
        if cap is None:
            cap = 3
        if rejection_count < cap:
            return "analyze_rca"
        else:
            return END
    return END

# Build Graph
builder = StateGraph(PipelineState)

# Add Nodes
builder.add_node("fetch_logs", fetch_logs_node)
builder.add_node("analyze_rca", analyze_rca_node)
builder.add_node("retrieve_context", retrieve_context_node)
builder.add_node("generate_patch", generate_patch_node)
builder.add_node("join_context_and_patch", join_context_and_patch)
builder.add_node("refine_patch", refine_patch_node)
builder.add_node("hitl_approval", hitl_approval_node)
builder.add_node("apply_fix", apply_fix_node)

# Set Entry
builder.set_entry_point("fetch_logs")

# Add Edges
builder.add_edge("fetch_logs", "analyze_rca")

# Conditional Routing after RCA
builder.add_conditional_edges(
    "analyze_rca",
    router_after_rca,
    {
        "retrieve_context": "retrieve_context",
        "generate_patch": "generate_patch",
        END: END
    }
)

# Join parallel paths
builder.add_edge("retrieve_context", "join_context_and_patch")
builder.add_edge("generate_patch", "join_context_and_patch")

# From Join to Refine Patch
builder.add_edge("join_context_and_patch", "refine_patch")

# Refine Patch to HITL
builder.add_edge("refine_patch", "hitl_approval")

# Conditional Routing after HITL
builder.add_conditional_edges(
    "hitl_approval",
    router_after_hitl,
    {
        "apply_fix": "apply_fix",
        "analyze_rca": "analyze_rca",
        END: END
    }
)

builder.add_edge("apply_fix", END)

# Compile
checkpointer = MemorySaver()
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["hitl_approval"]
)


def build_graph():
    """Return the compiled LangGraph (singleton with shared checkpointer)."""
    return graph
