from typing import Any
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from mcp_server.tools.github_tools import read_repo_file, list_repo_files
from agent.state import PipelineState

def retrieve_context_node(state: PipelineState) -> dict[str, Any]:
    try:
        pat = state.get("github_pat")
        repo = state.get("repo")
        affected_files = state.get("affected_files", [])
        
        if not pat or not repo:
            return {"error": "Missing github_pat or repo in state", "current_step": "error"}

        context_parts = []
        
        # 1. Directly fetch the affected_files content
        fetched_files = set()
        for filepath in affected_files:
            try:
                content = read_repo_file(github_pat=pat, repo=repo, file_path=filepath)
                context_parts.append(f"--- FILE: {filepath} ---\n{content}\n")
                fetched_files.add(filepath)
            except Exception as e:
                context_parts.append(f"--- FILE: {filepath} (Failed to load: {e}) ---\n")

        # 2. Query ChromaDB (Mocked/Simple version for now, relying on affected_files heuristics)
        # In a full implementation, we'd use rag.retriever here.
        # "If ChromaDB has no data yet (cold start): fetch top 5 most relevant files directly from GitHub"
        if not context_parts:
            # Fallback heuristic: Try to find files based on fix_type
            fix_type = state.get("fix_type")
            all_files = state.get("repo_files", [])
            
            candidates = []
            if fix_type == "dependency":
                candidates = [f for f in all_files if "requirements.txt" in f or "pyproject.toml" in f or "setup.py" in f or "package.json" in f]
            elif fix_type == "config":
                candidates = [f for f in all_files if f.endswith(".yml") or f.endswith(".yaml") or f.endswith(".json")]
            
            # Take top 5
            for filepath in candidates[:5]:
                if filepath not in fetched_files:
                    try:
                        content = read_repo_file(github_pat=pat, repo=repo, file_path=filepath)
                        context_parts.append(f"--- FILE: {filepath} ---\n{content}\n")
                    except Exception:
                        pass
        
        rag_context = "\n".join(context_parts)
        
        return {
            "rag_context": rag_context
        }

    except Exception as e:
        return {"error": f"Failed in retrieve_context_node: {str(e)}", "current_step": "error"}
