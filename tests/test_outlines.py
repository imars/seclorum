# tests/test_outlines.py
import os
import json
from seclorum.models.plan import Plan
from seclorum.models.managers.outlines import OutlinesModelManager

try:
    model_manager = OutlinesModelManager(model_name="mistral:latest")
    prompt = "Create a web-based JavaScript application for a drone racing game."
    print("INFO:__main__:Generating structured output")
    result = model_manager.generate(
        prompt,
        max_tokens=4096,
        temperature=0.3,
        function_call={"schema": Plan}  # Pass Plan class directly
    )
    result_dict = json.loads(result)
    print(f"INFO:__main__:Generated output: {json.dumps(result_dict, indent=2)}")
    print("DEBUG:__main__:Closing OutlinesModelManager")
except Exception as e:
    print(f"ERROR:__main__:Error: {str(e)}")
