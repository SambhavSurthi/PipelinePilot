import json
from typing import Any
from langchain_openai import ChatOpenAI
from agent.state import PipelineState
from agent.prompts.rca_prompt import rca_prompt_template

def analyze_rca_node(state: PipelineState) -> dict[str, Any]:
    try:
        api_key = state.get("openai_api_key")
        model_name = state.get("model_name", "gpt-4o")
        
        if not api_key:
            return {"error": "Missing openai_api_key in state", "current_step": "error"}

        llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=0.1)
        
        chain = rca_prompt_template | llm
        
        failed_step_str = json.dumps(state.get("failed_step", {}), indent=2)
        repo_files_str = "\n".join(state.get("repo_files", [])[:100]) # Pass up to 100 files
        
        response = chain.invoke({
            "failed_step": failed_step_str,
            "raw_logs": state.get("raw_logs", ""),
            "repo_files": repo_files_str
        })
        
        # Clean response content in case it has markdown ticks
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        rca_data = json.loads(content)
        
        return {
            "root_cause": rca_data.get("root_cause"),
            "fix_type": rca_data.get("fix_type"),
            "affected_files": rca_data.get("affected_files", []),
            "confidence": rca_data.get("confidence"),
            "fix_strategy": rca_data.get("fix_strategy"),
            "current_step": "rca_complete"
        }

    except Exception as e:
        return {"error": f"Failed in analyze_rca_node: {str(e)}", "current_step": "error"}
