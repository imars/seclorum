import os
import sys
import subprocess
import argparse
import glob

def copy_files_to_clipboard(file_patterns, summary=False):
    content = ""
    file_paths = []

    # Expand wildcards and collect all matching files
    for pattern in file_patterns:
        matching_files = glob.glob(pattern, recursive=True)
        if not matching_files:
            print(f"Warning: No files found matching pattern {pattern}")
        file_paths.extend(matching_files)

    if not file_paths:
        print("Error: No valid files found")
        return

    for path in file_paths:
        if not os.path.exists(path):
            print(f"Error: File {path} not found")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content += f"--- {path} [Last modified: {os.path.getmtime(path):.0f}] ---\n"
                content += f.read()
                content += "\n\n"
        except UnicodeDecodeError:
            print(f"Error: Could not read {path} (possibly not a text file)")
            continue

    if summary:
        content = content[:500] + "..." if len(content) > 500 else content

    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
    proc.communicate(input=content)
    print(f"Copied {len(file_paths)} file(s) to clipboard")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy file contents to clipboard.")
    parser.add_argument("files", nargs="+", help="Files or patterns to copy (supports wildcards)")
    parser.add_argument("--summary", action="store_true", help="Summarize content")
    args = parser.parse_args()

    copy_files_to_clipboard(args.files, args.summary)
