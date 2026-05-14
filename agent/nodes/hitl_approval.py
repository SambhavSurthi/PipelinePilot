from typing import Any
from agent.state import PipelineState

def hitl_approval_node(state: PipelineState) -> dict[str, Any]:
    # This is the interrupt node — LangGraph will pause here
    # The actual interrupt is handled in graph.py via interrupt_before=["hitl_approval"]
    # Return state unchanged except for the current step
    return {"current_step": "awaiting_approval"}
