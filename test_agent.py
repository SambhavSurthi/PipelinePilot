import os
from dotenv import load_dotenv
from unittest.mock import patch

# Load env vars
load_dotenv()

from agent.graph import graph
from agent.state import PipelineState

def run_test():
    # Setup mock state
    config = {"configurable": {"thread_id": "test_repo"}}
    
    # We will mock the github_tools and git_tools to avoid actual network calls
    with patch("agent.nodes.fetch_logs.list_workflow_runs") as mock_list_runs, \
         patch("agent.nodes.fetch_logs.get_workflow_run_logs") as mock_get_logs, \
         patch("agent.nodes.fetch_logs.get_failed_step_details") as mock_get_step, \
         patch("agent.nodes.fetch_logs.list_repo_files") as mock_list_files, \
         patch("agent.nodes.retrieve_context.read_repo_file") as mock_read_file, \
         patch("agent.nodes.apply_fix.Repo.clone_from") as mock_clone, \
         patch("agent.nodes.apply_fix.create_branch") as mock_create_branch, \
         patch("agent.nodes.apply_fix.apply_patch_and_commit") as mock_apply, \
         patch("agent.nodes.apply_fix.push_branch") as mock_push, \
         patch("agent.nodes.apply_fix.create_pull_request") as mock_pr:
         
        # Mock fetch_logs
        mock_list_runs.return_value = [{"id": 12345, "name": "Build", "status": "failure"}]
        mock_get_logs.return_value = "Traceback (most recent call last):\n  File \"main.py\", line 1, in <module>\n    import dotenv\nModuleNotFoundError: No module named 'dotenv'"
        mock_get_step.return_value = {
            "job_name": "build",
            "step_name": "Run tests",
            "log_excerpt": "ModuleNotFoundError: No module named 'dotenv'"
        }
        mock_list_files.return_value = ["main.py", "requirements.txt", "README.md"]
        
        # Mock retrieve_context
        def fake_read_repo_file(github_pat, repo, file_path, **kwargs):
            if file_path == "requirements.txt":
                return "requests==2.28.1\n"
            elif file_path == "main.py":
                return "import dotenv\nprint('Hello world')\n"
            return ""
        mock_read_file.side_effect = fake_read_repo_file
        
        # Mock apply_fix
        mock_create_branch.return_value = {"success": True}
        mock_apply.return_value = {"success": True, "commit_sha": "abcdef123456"}
        mock_push.return_value = {"success": True}
        mock_pr.return_value = {"success": True, "pr_url": "https://github.com/owner/repo/pull/1"}
        
        initial_state = {
            "user_message": "Fix this failure",
            "github_pat": os.getenv("GITHUB_PAT", "dummy_pat"),
            "repo": "owner/repo",
            "model_name": "gpt-4o",
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        }
        
        print("--- Running Graph up to HITL ---")
        for event in graph.stream(initial_state, config=config, stream_mode="values"):
            step = event.get("current_step")
            print(f"Step: {step}")
            if event.get("error"):
                print(f"Error: {event.get('error')}")
                
        # Get current state
        state = graph.get_state(config)
        print("\n--- Graph Paused at HITL ---")
        print("Root Cause:", state.values.get("root_cause"))
        print("Proposed Patch:", state.values.get("proposed_patch"))
        print("Patch Explanation:", state.values.get("patch_explanation"))
        
        print("\n--- Simulating User Approval ---")
        # Update state with user decision
        graph.update_state(config, {"user_decision": "approve", "current_step": "user_approved"})
        
        # Resume graph
        print("--- Resuming Graph ---")
        for event in graph.stream(None, config=config, stream_mode="values"):
            step = event.get("current_step")
            print(f"Step: {step}")
            if event.get("error"):
                print(f"Error: {event.get('error')}")
                
        final_state = graph.get_state(config)
        print("\n--- Final State ---")
        print("Branch Name:", final_state.values.get("branch_name"))
        print("Commit SHA:", final_state.values.get("commit_sha"))
        print("PR URL:", final_state.values.get("pr_url"))

if __name__ == "__main__":
    run_test()
