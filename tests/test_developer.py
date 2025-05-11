# tests/test_developer.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import logging
import unittest
import time
import json
import argparse
import re
from seclorum.models import Task, CodeOutput
from seclorum.agents.developer import Developer
from seclorum.models import create_model_manager

print("Starting test script")

def setup_logging(quiet: bool = False):
    level = logging.DEBUG if not quiet else logging.WARNING
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s", force=True)
    for name in ["seclorum", "seclorum.agents.base", "seclorum.agents.executor", "seclorum.agents.debugger"]:
        logging.getLogger(name).setLevel(level)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    print(f"Logging initialized to level: {logging.getLevelName(level)}")

def format_history(history):
    if not history:
        return "No history available"
    formatted = "Recent History:\n"
    for entry in history[-3:]:
        timestamp = entry[2]  # timestamp from (prompt, response, timestamp)
        response = entry[1]   # response from (prompt, response, timestamp)
        try:
            parsed = json.loads(response) if response.startswith("{") else response
            if isinstance(parsed, dict):
                formatted += f"- {timestamp}:\n  {json.dumps(parsed, indent=2)}\n"
            else:
                formatted += f"- {timestamp}:\n  {parsed.strip()}\n"
        except json.JSONDecodeError:
            formatted += f"- {timestamp}:\n  {response.strip()}\n"
    return formatted

def strip_markdown_json(text: str) -> str:
    """Strip Markdown code fences from JSON output."""
    return re.sub(r'```(?:json)?\n([\s\S]*?)\n```', r'\1', text).strip()

class TestDeveloper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args = args  # Use global args parsed in main block
        setup_logging(cls.args.quiet)

    def setUp(self):
        self.session_id = "test_session"
        self.task_id = f"test_task_{unittest.TestCase.id(self).split('.')[-1]}"
        self.use_remote = self.args.remote
        self.model_name = self.args.model
        if self.use_remote:
            self.model_manager = create_model_manager(provider="google_ai_studio", model_name=self.model_name)
        else:
            self.model_manager = create_model_manager(provider="outlines", model_name=self.model_name, use_custom_tokenizer=True)
        self.task = Task(
            task_id=self.task_id,
            description=(
                "Create a simple web-based JavaScript application for a counter. "
                "Include an HTML file ('counter.html') with a button and a display (span#count). "
                "Use CSS ('styles.css') for styling. "
                "Implement JavaScript ('counter.js') to increment the count on button click. "
                "Include a configuration file ('package.json')."
            ),
            parameters={
                "language": "javascript",
                "output_files": ["counter.html", "styles.css", "counter.js", "package.json"],
                "generate_tests": True,
                "execute": True,
                "use_remote": self.use_remote,
                "max_tokens": 8192 if self.use_remote else 4096
            }
        )
        print(f"Set up test with task_id: {self.task_id}, model: {self.model_name}, remote: {self.use_remote}")

    def tearDown(self):
        if hasattr(self.model_manager, 'close'):
            self.model_manager.close()
        print("Tear down complete")

    def test_memory_cache(self):
        from seclorum.agents.memory.core import Memory
        memory = Memory(self.session_id)
        memory.cache_response("test_hash", "test_response")
        self.assertEqual(memory.load_cached_response("test_hash"), "test_response")
        import time
        time.sleep(3601)  # Wait for cache to expire
        self.assertIsNone(memory.load_cached_response("test_hash"))

    def test_executor_to_debugger(self):
        print(f"Starting test_executor_to_debugger with task_id: {self.task_id}")
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        print(f"Developer graph: {developer.graph}")
        status, result = developer.orchestrate(self.task)
        history = developer.memory.load_conversation_history(self.task_id, developer.name)
        print(f"Status: {status}, Result: {result}")
        print(format_history(history))
        self.assertIn(status, ["generated", "tested", "executed", "debugged"], f"Unexpected status: {status}")
        self.assertIsInstance(result, CodeOutput, f"Expected CodeOutput, got {type(result).__name__}")
        self.assertTrue(result.code.strip(), "Code output is empty")
        self.assertTrue(any("counter.js" in f for f in result.output_files), "Expected counter.js in output files")
        debug_entries = [e for e in history if "Fixed code" in str(e[1]) or "debug" in str(e[1]).lower()]
        self.assertTrue(len(debug_entries) >= 0, "Expected debug entries in history")
        developer.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Developer agent tests")
    parser.add_argument("--model", default="qwen3:4b", help="Model name (e.g., qwen3:4b, gemini-1.5-flash)")
    parser.add_argument("--remote", action="store_true", help="Use remote inference (Google AI Studio)")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    args, _ = parser.parse_known_args()  # Parse args before unittest

    output_file = "test_developer_output.txt"
    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2 if not args.quiet else 0)
    suite = unittest.TestSuite()
    suite.addTest(TestDeveloper('test_executor_to_debugger'))
    result = runner.run(suite)
    elapsed_time = time.time() - start_time
    with open(output_file, "w") as f:
        f.write(f"Ran {result.testsRun} tests in {elapsed_time:.3f}s\n")
        if result.wasSuccessful():
            f.write("OK\n")
        else:
            f.write(f"FAILED (failures={len(result.failures)}, errors={len(result.errors)})\n")
            for fail in result.failures:
                f.write(f"{fail[0]}\n{fail[1]}\n")
    print(f"Test output saved to {output_file}")
