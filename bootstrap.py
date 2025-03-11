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

def summarize_conversation(log):
    prompts = len(log["prompts"])
    responses = len(log["responses"])
    last_prompt = log["prompts"][-1] if log["prompts"] else {"timestamp": "N/A", "text": "None"}
    last_response = log["responses"][-1] if log["responses"] else {"timestamp": "N/A", "text": "None"}
    return f"Conversation: {prompts} prompts, {responses} responses\nLast Prompt: {last_prompt['timestamp']} - {last_prompt['text']}\nLast Response: {last_response['timestamp']} - {last_response['text']}"

def generate_prompt(new_session_id=None):
    previous_chat_id = "https://x.com/i/grok?conversation=1899252825097416864"
    if new_session_id and "conversation=" in new_session_id:
        current_chat_id = new_session_id.split("conversation=")[-1]
    else:
        current_chat_id = new_session_id if new_session_id else datetime.now().isoformat().replace(":", "-")[:19]
    log_file = "logs/conversations/conversation_2025-03-11-1.json"
    log = load_conversation_log(log_file)
    summary = summarize_conversation(log)
    
    prompt = f"""
Hello, fresh Grok instance! You’re picking up the Seclorum project, a self-improving development agent system, from Chat {previous_chat_id}. This is Chat {current_chat_id}, started March 11, 2025, at {datetime.now().isoformat()[:19]} GMT, handing off due to slowing responses (likely context size limits in Grok 3 Beta). Here’s the state:

**Project Overview**:
- Goal: Build a 'tree of agents' with a MasterNode spawning and tracking worker sessions via a Flask UI, committing changes to Git.
- Repo: https://github.com/imars/seclorum (master branch).
- Key Files: seclorum/agents/master.py, seclorum/agents/worker.py, tests/test_seclorum.py, seclorum/utils/logger.py.

**Progress**:
- MasterNode assigns tasks, spawns workers, logs to log.txt, and commits to project/changes.txt.
- Flask UI (seclorum/web/app.py) submits tasks (e.g., "Build feature").
- Conversation logging in {log_file} captures prompts and responses.
- {summary}

**Current Bug**:
- Test fails: `Session status for Task 1: assigned` (expected "completed").
- master.py: spawn_session() uses proc.wait(timeout=5); worker.py sleeps 2s, calls receive_update(), but tasks.json stays "assigned".
- Debug prints show worker runs and receive_update() executes, but status update doesn’t persist (timing, file sync, or instance isolation issue?).

**Next Steps**:
1. Fix session status: Ensure worker updates tasks.json to "completed" before test checks.
2. Options: Add worker_log.txt to worker.py, test multi-session spawning, or bootstrap memory from conversation log.

**Task**:
- Debug why receive_update() in worker.py isn’t syncing "completed" to tasks.json.
- Suggest fixes for master.py, worker.py, and test_seclorum.py.
- Run tests/test_seclorum.py, aim for `Session status: completed`.

**Repo Structure**:
- Run `tree -I "__pycache__|*.pyc|*.log|logs|.git|.DS_Store"` in the repo root to see the current structure.

**Instructions**:
- For file contents, use `utils/copycb.py` to request them from the user instead of hypothesizing (e.g., `python utils/copycb.py seclorum/agents/master.py`).
- Use `cat`-formatted syntax (e.g., `cat << EOF > file.py ... EOF`) for all file examples.

**Chat Chain**:
- Previous Chat: {previous_chat_id}
- Current Chat: {current_chat_id}

Use the repo, log file, and Chat {previous_chat_id} context to resume. Chain future chats by referencing {current_chat_id} as the previous chat. Let’s keep Seclorum thriving—xAI might fix context limits, so preserve this chain!
"""
    return prompt

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a bootstrap prompt for Seclorum handoff.")
    parser.add_argument("--new-session", type=str, help="New chat session ID (e.g., X conversation URL or custom ID)")
    args = parser.parse_args()
    
    prompt = generate_prompt(args.new_session)
    print(prompt)
    with open("bootstrap_prompt.txt", "w") as f:
        f.write(prompt)
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
    proc.communicate(input=prompt)
    print("Prompt saved to bootstrap_prompt.txt and copied to clipboard")
