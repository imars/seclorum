import os
from datetime import datetime
import pyperclip
import argparse
import sys

def copy_files_to_clipboard(file_paths, summary=False):
    """Copy contents or summaries of specified files to the clipboard with timestamps."""
    if not file_paths:
        return "No files provided to copy."
    
    content = []
    missing_files = []
    for path in file_paths:
        if os.path.exists(path):
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(path))
                mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
                with open(path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    if summary:
                        # Take first 3 lines or less, truncate to 100 chars per line
                        preview = "\n".join(line[:100] for line in file_content.splitlines()[:3])
                        content.append(f"--- {path} [Last modified: {mod_time_str}] ---\n{preview}\n[...]\n")
                    else:
                        content.append(f"--- {path} [Last modified: {mod_time_str}] ---\n{file_content}\n")
            except Exception as e:
                content.append(f"--- {path} ---\nError reading file: {str(e)}\n")
        else:
            missing_files.append(path)
    
    if missing_files:
        print(f"Warning: Files not found or inaccessible: {', '.join(missing_files)}")
    
    if not content:
        return "No valid file contents to copy."
    
    full_content = "\n".join(content)
    try:
        pyperclip.copy(full_content)
        return f"Copied {len(file_paths) - len(missing_files)} file(s) to clipboard"
    except Exception as e:
        return f"Failed to copy to clipboard: {str(e)} (ensure 'pyperclip' is installed with 'pip install pyperclip')"

def get_ordered_files(directory):
    """Get development files in the directory sorted by modification time, excluding non-dev files."""
    file_info = []
    # Patterns to exclude
    exclude_dirs = {"__pycache__", ".git", "logs"}
    exclude_files = {".gitignore", ".DS_Store"}  # Common non-dev files
    exclude_exts = {".pyc", ".log", ".tmp"}      # Common non-dev extensions
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        if any(exclude in root for exclude in exclude_dirs):
            continue
        for file in files:
            path = os.path.join(root, file)
            # Skip excluded files and extensions
            if (file in exclude_files or 
                any(file.endswith(ext) for ext in exclude_exts)):
                continue
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(path))
                file_info.append((path, mod_time))
            except Exception:
                continue
    
    file_info.sort(key=lambda x: x[1], reverse=True)  # Sort by mod time, newest first
    return [path for path, _ in file_info]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy development files to clipboard")
    parser.add_argument("--most-recent", type=int, nargs="?", const=-1, help="Copy the N most recently modified dev files in the current directory (omit N for all files)")
    parser.add_argument("--summary", action="store_true", help="Copy a summary of each file instead of full contents")
    parser.add_argument("files", nargs="*", help="List of files to copy (if --most-recent is not used)")
    args = parser.parse_args()
    
    if args.most_recent is not None:
        if args.files:
            print("Warning: --most-recent ignores provided file list; scanning current directory.")
        # Scan current directory (.) for dev files
        all_files = get_ordered_files(".")
        # Select N most recent or all if N is not specified (const=-1 triggers all)
        selected_files = all_files[:args.most_recent] if args.most_recent > 0 else all_files
        result = copy_files_to_clipboard(selected_files, summary=args.summary)
    else:
        if not args.files:
            print("Error: No files specified. Usage: python copycb.py file1 file2 ... [--most-recent [N]] [--summary]")
            sys.exit(1)
        selected_files = args.files
        result = copy_files_to_clipboard(selected_files, summary=args.summary)
    
    print(result)
