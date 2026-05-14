from langchain_core.prompts import ChatPromptTemplate

system_prompt = """You are an expert software engineer and CI/CD specialist.
Your task is to generate a patch to fix the pipeline failure based on the root cause analysis and provided file context.

You MUST return ONLY a valid JSON object matching the following structure exactly, with NO markdown formatting, NO backticks, and NO additional text.
{{
  "patches": [
    {{
      "filename": "path/to/file.ext",
      "original_content": "The exact original lines being replaced",
      "patched_content": "The exact new lines to insert",
      "explanation": "Why this specific change was made"
    }}
  ],
  "overall_explanation": "A high-level explanation of the patch for the PR description",
  "confidence": "high|medium|low"
}}

Here is the root cause analysis:
{root_cause_analysis}

Here is the relevant file context (content of files you can modify):
{file_context}

Return ONLY the JSON. Do not explain outside the JSON.
"""

patch_prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("user", "Please generate the patch JSON based on the analysis and context.")
])
