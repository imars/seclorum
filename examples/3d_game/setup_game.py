# examples/3d_game/setup_game.py
from seclorum.agents.aggregate import AbstractAggregate
from seclorum.agents.architect import Architect
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.debugger import Debugger
from seclorum.tasks import Task

def main():
    task = Task(task_id="game_task", description="Create a 3D web browser game using Three.js")
    developer = AbstractAggregate("dev_game")

    developer.add_agent(Architect("game_task"))
    developer.add_agent(Generator("game_task"), [("Architect_game_task", {"status": "planned"})])
    developer.add_agent(Tester("game_task"), [("Generator_game_task", {"status": "generated"})])
    developer.add_agent(Executor("game_task"), [("Tester_game_task", {"status": "tested"}), ("Generator_game_task", {"status": "generated"})])
    developer.add_agent(Debugger("game_task"), [("Executor_game_task", {"status": "tested", "passed": False})])

    status, result = developer.orchestrate(task)
    print(f"Status: {status}, Result: {result}")

if __name__ == "__main__":
    main()
