import click
from seclorum.core.filesystem import FileSystemManager
from seclorum.core.checkpoint import CheckpointManager
from seclorum.core.bootstrap import Bootstrap

@click.group()
def main():
    pass

@main.command()
@click.argument("path", default="./project")
@click.argument("filename")
@click.argument("content")
def save(path, filename, content):
    fs = FileSystemManager(path)
    fs.save_file(filename, content)
    click.echo(f"Saved {filename}")

@main.command()
@click.argument("path", default="./project")
@click.argument("chat_url")
@click.option("--chat-messages", default="[]", help="JSON list of chat messages")
@click.option("--edited-files", default="[]", help="JSON list of edited files")
def checkpoint(path, chat_url, chat_messages, edited_files):
    import json
    cp_manager = CheckpointManager(path)
    messages = json.loads(chat_messages)
    files = json.loads(edited_files)
    hash = cp_manager.create_checkpoint(chat_url, messages, files)
    click.echo(f"Checkpoint created with hash: {hash}")

@main.command()
@click.argument("path", default="./project")
def bootstrap(path):
    bootstrap = Bootstrap(path)
    prompt = bootstrap.generate_prompt()
    click.echo("Bootstrap Prompt:\n")
    click.echo(prompt)
