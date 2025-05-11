# summarise.py
import sys
from collections import defaultdict

def summarize_log():
    # Dictionary to store prefix -> {line: count}
    log_index = defaultdict(lambda: defaultdict(int))
    # Dictionary to store prefix -> first occurrence of each unique line
    first_occurrence = defaultdict(dict)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        # Extract prefix (everything before the first colon)
        if ':' in line:
            prefix, content = line.split(':', 1)
            prefix = prefix.strip()
            content = content.strip()
        else:
            # Handle lines without a colon (use entire line as prefix)
            prefix = line
            content = ""

        # Full line for tracking
        full_line = f"{prefix}: {content}" if content else prefix

        # Increment count for this line under the prefix
        log_index[prefix][full_line] += 1

        # Store the first occurrence if not already stored
        if full_line not in first_occurrence[prefix]:
            first_occurrence[prefix][full_line] = True
            count = log_index[prefix][full_line]
            # Output the line with count (real-time)
            if count > 1:
                print(f"{full_line}[{count}]")
            else:
                print(full_line)
            sys.stdout.flush()  # Ensure real-time output

if __name__ == "__main__":
    try:
        summarize_log()
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
