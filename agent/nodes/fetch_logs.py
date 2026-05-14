from typing import Any
import sys
import os

# Add the project root to the python path to import mcp_server tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from mcp_server.tools.github_tools import (
    list_workflow_runs,
    get_workflow_run_logs,
    get_failed_step_details,
    list_repo_files,
)
from agent.state import PipelineState

def fetch_logs_node(state: PipelineState) -> dict[str, Any]:
    try:
        pat = state.get("github_pat")
        repo = state.get("repo")
        
        if not pat or not repo:
            return {"error": "Missing github_pat or repo in state"}

        # 1. Get recent failed workflow runs
        runs = list_workflow_runs(github_pat=pat, repo=repo, status="failure", limit=1)
        if not runs:
            return {"error": "No recent failed workflow runs found", "current_step": "error"}
            
        latest_failed_run = runs[0]
        run_id = latest_failed_run["id"]

        # 2. Get full logs
        raw_logs = get_workflow_run_logs(github_pat=pat, repo=repo, run_id=run_id)

        # 3. Get specific failed step info
        failed_step = get_failed_step_details(github_pat=pat, repo=repo, run_id=run_id)

        # 4. Get repo files (.py, .yml, .toml, .txt, .json, .cfg, .ini)
        allowed_extensions = [".py", ".yml", ".yaml", ".toml", ".txt", ".json", ".cfg", ".ini"]
        repo_files = list_repo_files(github_pat=pat, repo=repo, ref="main", extensions=allowed_extensions)

        return {
            "failed_run_id": run_id,
            "raw_logs": raw_logs,
            "failed_step": failed_step,
            "repo_files": repo_files,
            "current_step": "logs_fetched"
        }

    except Exception as e:
        return {"error": f"Failed in fetch_logs_node: {str(e)}", "current_step": "error"}
