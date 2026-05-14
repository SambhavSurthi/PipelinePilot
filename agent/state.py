from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages

class PipelineState(TypedDict):
    # Input
    user_message: str
    github_pat: str
    repo: str                    # owner/repo
    model_name: str
    openai_api_key: str
    
    # Fetched data
    failed_run_id: Optional[int]
    raw_logs: Optional[str]
    failed_step: Optional[dict]  # {job_name, step_name, log_excerpt}
    repo_files: Optional[list[str]]    # list of file paths in repo
    
    # Analysis
    root_cause: Optional[str]          # plain English explanation
    fix_type: Optional[str]            # "dependency" | "syntax" | "config" | "test" | "unknown"
    affected_files: Optional[list[str]]
    confidence: Optional[str]          # "high" | "medium" | "low"
    fix_strategy: Optional[str]
    
    # RAG context
    rag_context: Optional[str]         # retrieved relevant file contents
    
    # Patch
    proposed_patch: Optional[dict]     # {filename: {original: str, patched: str, unified_diff: str}}
    patch_explanation: Optional[str]   # human-readable explanation of the fix
    
    # HITL
    user_decision: Optional[str]       # "approve" | "reject" | "modify"
    user_feedback: Optional[str]       # if rejected, user's feedback
    rejection_count: int               # track retry attempts
    max_retries: Optional[int]          # max reject→retry cycles (UI slider)
    
    # Output
    branch_name: Optional[str]
    commit_sha: Optional[str]
    pr_url: Optional[str]
    
    # Chat history
    messages: Annotated[list, add_messages]
    
    # Error handling
    error: Optional[str]
    current_step: Optional[str]        # for UI status display
