# tests/test_guidance.py
import os
import json
import guidance
from seclorum.models.managers.guidance import GuidanceModelManager

schema = '''
{
    "subtasks": [
        {
            "description": "{{gen 'description' max_tokens=50 temperature=0.3}}",
            "language": "{{select 'language' options=['html', 'css', 'javascript']}}",
            "parameters": {
                "output_files": ["{{gen 'output_file' pattern='[a-zA-Z0-9_]+\.[a-z]+' max_tokens=20 temperature=0.3}}"]
            }
        }
    ]
}
'''

# Test GuidanceModelManager with mistral:latest
try:
    model_manager = GuidanceModelManager(model_name="mistral:latest")
    prompt = "Create a web-based JavaScript application for a drone racing game."
    result = model_manager.generate(
        prompt,
        max_tokens=4096,
        temperature=0.3,
        function_call={"schema": schema}
    )
    result_dict = json.loads(result)
    print(json.dumps(result_dict, indent=2))
except Exception as e:
    print(f"Error: {str(e)}")
