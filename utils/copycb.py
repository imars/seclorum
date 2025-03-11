import os
import sys
import subprocess
import argparse

def copy_files_to_clipboard(file_paths, summary=False):
    content = ""
    for path in file_paths:
        if not os.path.exists(path):
            print(f"Error: File {path} not found")
            continue
        with open(path, "r") as f:
            content += f"--- {path} [Last modified: {os.path.getmtime(path):.0f}] ---\n"
            content += f.read()
            content += "\n\n"
    if summary:
        content = content[:500] + "..." if len(content) > 500 else content
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
    proc.communicate(input=content)
    print(f"Copied {len(file_paths)} file(s) to clipboard")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy file contents to clipboard.")
    parser.add_argument("files", nargs="+", help="Files to copy")
    parser.add_argument("--summary", action="store_true", help="Summarize content")
    args = parser.parse_args()
    
    copy_files_to_clipboard(args.files, args.summary)
