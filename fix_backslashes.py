import argparse
import os
import re

def fix_backslashes(file_path):
    """
    Remove unwanted backslashes from a file that cause SyntaxErrors, e.g., in .format\(arg\).
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        return

    # Read the original content
    with open(file_path, "r") as f:
        content = f.read()

    # Replace backslashes before parentheses in .format() calls
    # e.g., .format\(arg\) -> .format(arg)
    fixed_content = re.sub(r'\.format\\\(.*?\)', lambda m: m.group(0).replace('\\', ''), content)

    # Check if any changes were made
    if content == fixed_content:
        print(f"No backslashes found to fix in '{file_path}'.")
        return

    # Write the fixed content back to the file
    with open(file_path, "w") as f:
        f.write(fixed_content)
    
    print(f"Fixed backslashes in '{file_path}'. File updated successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove unwanted backslashes from a Python file.")
    parser.add_argument("file", type=str, help="Path to the file to fix (e.g., bootstrap.py)")
    args = parser.parse_args()

    fix_backslashes(args.file)
