import sys
print("Python path:", sys.path)
import bootstrap
print("Bootstrap module path:", bootstrap.__file__)
import unittest
import os
import subprocess
from bootstrap import generate_prompt, commit_handoff

class TestBootstrap(unittest.TestCase):
    def test_preamble_style(self):
        prompt = generate_prompt("1900257132001517690", "1900718979536052318", preamble_only=True)
        self.assertIn("Hello, fresh Grok instance!", prompt)
        self.assertIn("I’ll brief you in the next prompt.", prompt)
        self.assertNotIn("Project Overview:", prompt)

    def test_full_prompt_style(self):
        prompt = generate_prompt("1900257132001517690", "1900718979536052318")
        self.assertIn("Project Overview:\n* Goal:", prompt)
        self.assertIn("Progress:\n* Redis installed", prompt)
        self.assertIn("Next Steps:\n1. Add cross-session memory", prompt)
        self.assertIn("Chat Chain:\n* Previous:", prompt)

    def test_commit_handoff(self):
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["touch", "test_file"], check=True)
        commit_handoff("1900257132001517690", "1900718979536052318")
        result = subprocess.run(["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True)
        self.assertIn("Agent handoff", result.stdout)

if __name__ == "__main__":
    unittest.main()
