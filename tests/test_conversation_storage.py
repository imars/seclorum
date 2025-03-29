import os
from seclorum.memory.core import ConversationMemory

def test_conversation_storage():
    # Test SQLite (default)
    session_id = "test_sqlite"
    mem_sqlite = ConversationMemory(session_id=session_id, use_json=False)
    mem_sqlite.save(prompt="Hello", response="Hi there", task_id="1")
    history_sqlite = mem_sqlite.load_conversation_history(task_id="1")
    assert "User: Hello" in history_sqlite
    assert "Agent: Hi there" in history_sqlite

    # Test JSON
    mem_json = ConversationMemory(session_id=session_id, use_json=True)
    mem_json.save(prompt="Hey", response="Yo", task_id="2")
    history_json = mem_json.load_conversation_history(task_id="2")
    assert "User: Hey" in history_json
    assert "Agent: Yo" in history_json

    # Cleanup
    os.remove(mem_sqlite.db_file)
    os.remove(mem_json.json_file)

if __name__ == "__main__":
    test_conversation_storage()
    print("Conversation storage tests passed!")
