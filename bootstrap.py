import json
import os
import argparse
import subprocess
from datetime import datetime

def load_conversation_log(log_file):
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return json.load(f)
    return {"prompts": [], "responses": []}

def format_conversation(log):
    prompts = log["prompts"]
    responses = log["responses"]
    recent_prompts = prompts[-5:] if len(prompts) > 5 else prompts
    recent_responses = responses[-5:] if len(responses) > 5 else responses
    summary = "* Conversation: {} prompts, {} responses\n".format(len(prompts), len(responses))
    summary += "Recent Prompts:\n"
    for p in recent_prompts:
        summary += "* {}: {}\n".format(p["timestamp"], p["text"])
    summary += "Recent Responses:\n"
    for r in recent_responses:
        summary += "* {}: {}\n".format(r["timestamp"], r["text"])
    return summary.rstrip()

def commit_handoff(previous_session_id, new_session_id, no_git=False):
    commit_msg = "Agent handoff from session {} to {} on {}".format(
        previous_session_id, new_session_id, datetime.now().isoformat()
    )
    if not no_git:
        subprocess.run(["git", "add", "."], check=True)
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        else:
            subprocess.run(["git", "commit", "--allow-empty", "-m", commit_msg], check=True)
        print("Committed handoff: {}".format(commit_msg))
    else:
        print("Git operations skipped (--no-git enabled): {}".format(commit_msg))

def load_config(config_file="bootstrap_config.json"):
    default_config = {
        "recent_prompts": [],
        "recent_responses": [],
        "key_files": "seclorum/agents/master.py, seclorum/agents/worker.py, tests/test_seclorum.py, seclorum/utils/logger.py, seclorum/cli/commands.py, bootstrap.py",
        "progress": [
            "Redis installed and working.",
            "Agent lifecycle (start and stop) management added.",
            "MasterNode assigns tasks, spawns workers, logs to log.txt, and commits to project/changes.txt.",
            "Flask UI (seclorum/web/app.py) submits tasks (e.g., \"Build feature\").",
            "Conversation logging in logs/conversations/conversation_2025-03-11-1.json captures prompts and responses.",
            "Fixed 'assigned'/'completed' bug in tests/test_seclorum.py (status now syncs via load_tasks).",
            "Added worker_log.txt to worker.py for enhanced logging.",
            "Enabled multi-session spawning in master.py with active_sessions tracking."
        ],
        "next_steps": [
            "Add cross-session memory. Embed agent and user conversations in the background. Store all conversations.",
            "Refine and add UI elements:\n    1. The user text entry box should resize vertically upwards as new lines or text are added.\n    2. Since we’re developing a graph of agents to work on projects, I’d also like a Gantt chart display that might itself have tabs for each project. This display can either be in a third panel on the chat screen or as a tab in the Agent Output panel (the agents panel would then be renamed to Agents). I’m leaning towards a third panel.",
            "Improve bootstrapping:\n    1. Reduce the number of edits on bootstrap.py by storing sections in JSON. Recent prompts and responses need to be more fleshed out.\n    2. bootstrap.py should inform the new agent to immediately perform a commit before changing any file. The commit should mention that a handoff has occurred.\n    3. The bootstrapping process takes several prompts or actions (since prompts can be edited) from the user, so we’ll need to add a --preamble option:\n        1. Preamble: Our current short introduction, mentioning that the next prompt (or edit) will contain the rest of the bootstrap. Example: python bootstrap.py --preamble \"Hello, fresh Grok instance! You’re picking up the Seclorum project, a self-improving development agent system, from Chat <previous session id>. I’ll brief you in the next prompt.\"\n        2. The bootstrap proper; Example: python bootstrap.py --new-session <session id recovered from the previous step>"
        ],
        "tasks": ["Add memory. Upgrade bootstrapping. Tidy up UI and app, and enhance features."],
        "repo_structure": "Run tree -I \"__pycache__|*.pyc|*.log|logs|.git|.DS_Store|*.pid\" in the repo root to see the current structure:\n<insert tree output here>",
        "instructions": [
            "For file contents, use utils/copycb.py to request them from the user instead of hypothesizing (e.g., python utils/copycb.py seclorum/agents/master.py). Don't assume anything if overwriting files, but it's ok to assume or hypothesise if calling unknown files.",
            "Use cat-formatted syntax (e.g., cat << EOF > file.py ... EOF) for all file examples.",
            "Output any single commands in a code box or for easy of copying.",
            "Favour a test based approach and save new tests in test/. We should encapsulate a batch of test steps into single test script, as we test different aspects of our project."
        ],
        "insights": [
            "This section was added manually, needs improvement, and should be automated.",
            "Be very careful of Python packaging issues; we’ve spent a lot of time hunting down basic packaging errors.",
            "Use proper escaping and punctuation in Heredoc, especially with Jinja2 syntax. Use quoted Heredoc (<< 'EOF').",
            "We’re using mixins, so be aware of potential multiple inheritance issues."
        ]
    }
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
        default_config.update(config)
    return default_config

def generate_prompt(previous_session_id, new_session_id, preamble_only=False):
    current_date = datetime.now().strftime("%B %d, %Y")
    previous_chat_url = "https://x.com/i/grok?conversation={}".format(previous_session_id)
    current_chat_url = "https://x.com/i/grok?conversation={}".format(new_session_id)
    log_file = "logs/conversations/conversation_2025-03-11-1.json"  # TODO: Make dynamic
    log = load_conversation_log(log_file)
    conversation_summary = format_conversation(log)
    config = load_config()

    if preamble_only:
        return "Hello, fresh Grok instance! You’re picking up the Seclorum project, a self-improving development agent system, from Chat {}. I’ll brief you in the next prompt.".format(previous_chat_url)

    # Dynamically fetch repo structure
    repo_structure = config["repo_structure"]
    if "<insert tree output here>" in repo_structure:
        try:
            tree_output = subprocess.check_output(
                ["tree", "-I", "__pycache__|*.pyc|*.log|logs|.git|.DS_Store|*.pid"],
                text=True
            )
            repo_structure = repo_structure.replace("<insert tree output here>", tree_output.rstrip())
        except subprocess.CalledProcessError:
            repo_structure = repo_structure.replace("<insert tree output here>", "(tree output unavailable)")

    # Build prompt as a raw string with .format()
    prompt = """Hello, fresh Grok instance! You’re taking over the Seclorum project (https://github.com/imars/seclorum), an agentic, self-improving development system (a graph of agents), from the chat at {0}, which is handing off to you due to slowing responses—likely caused by context size limits in Grok 3 Beta.
You are the chat at {1}, started on {2}. Please review the following state for important instructions and helpful insights. Here’s the state:

Project Overview:
* Goal: Build a 'graph of agents' with a MasterNode spawning and tracking worker sessions via a Flask UI, committing changes to Git.
* Repo: https://github.com/imars/seclorum (master branch).
* Current Key Files: {3}

Progress:
* {4}

Current Bug:
* There are no known bugs at the moment.

Next Steps:
{5}
Tasks:
* {6}

Repo Structure:
* {7}

Instructions:
* {8}

Insights and surprises
* {9}

Chat Chain:
* Previous: {0}
* Current: {1}

Use the repo, log file, and Chat {0} context to resume. Chain future chats by referencing Current: {1} (this chat) as the previous chat. Let’s keep Seclorum healthy and thriving—xAI might fix context limits, so preserve this chain!""".format(
        previous_chat_url,
        current_chat_url,
        current_date,
        config["key_files"],
        "* ".join(config["progress"] + [conversation_summary]),
        "".join(["{}. {}\n".format(i + 1, step) for i, step in enumerate(config["next_steps"])]),
        "* ".join(config["tasks"]),
        repo_structure,
        "* ".join(config["instructions"]),
        "* ".join(config["insights"])
    )
    return prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a bootstrap prompt for Seclorum handoff.")
    parser.add_argument("--previous-session", type=str, default="1900257132001517690", help="Previous chat session ID")
    parser.add_argument("--new-session", type=str, default="1900718979536052318", help="New chat session ID")
    parser.add_argument("--preamble", action="store_true", help="Output preamble only")
    parser.add_argument("--no-git", action="store_true", help="Skip Git operations (for testing)")
    args = parser.parse_args()

    if not args.preamble:
        commit_handoff(args.previous_session, args.new_session, args.no_git)

    prompt = generate_prompt(args.previous_session, args.new_session, args.preamble)
    with open("bootstrap_prompt.txt", "w") as f:
        f.write(prompt)
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
    proc.communicate(input=prompt)
    print("Prompt saved to bootstrap_prompt.txt and copied to clipboard")
