from typing import Any
import json
import difflib
from langchain_openai import ChatOpenAI
from agent.state import PipelineState
from agent.prompts.patch_prompt import patch_prompt_template

def refine_patch_node(state: PipelineState) -> dict[str, Any]:
    try:
        api_key = state.get("openai_api_key")
        model_name = state.get("model_name", "gpt-4o")
        
        if not api_key:
            return {"error": "Missing openai_api_key in state", "current_step": "error"}

        llm = ChatOpenAI(api_key=api_key, model=model_name, temperature=0.1)
        chain = patch_prompt_template | llm
        
        rca_summary = {
            "root_cause": state.get("root_cause"),
            "fix_type": state.get("fix_type"),
            "fix_strategy": state.get("fix_strategy")
        }
        
        # In refine, we definitely have rag_context
        response = chain.invoke({
            "root_cause_analysis": json.dumps(rca_summary, indent=2),
            "file_context": state.get("rag_context", "No context available.")
        })
        
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        patch_data = json.loads(content)
        
        proposed_patch = {}
        for p in patch_data.get("patches", []):
            filename = p.get("filename")
            original = p.get("original_content", "")
            patched = p.get("patched_content", "")
            
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}"
            )
            proposed_patch[filename] = {
                "original": original,
                "patched": patched,
                "unified_diff": "".join(diff),
                "explanation": p.get("explanation", "")
            }
            
        return {
            "proposed_patch": proposed_patch,
            "patch_explanation": patch_data.get("overall_explanation"),
            "current_step": "patch_ready",
        }

    except Exception as e:
        return {"error": f"Failed in refine_patch_node: {str(e)}", "current_step": "error"}
