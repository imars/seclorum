# scripts/summarise.sh
#!/bin/zsh

# Summarize log output in real-time, indexing by first word or connected word up to ':'
# Usage: python -B tests/test_outlines.py --model qwen3:0.6b | ./scripts/summarise.sh

awk '
BEGIN {
    # Initialize an associative array to track counts and first lines
}
{
    # Extract index (first word or connected word up to ":")
    if (match($0, /^[^:]+:/)) {
        idx = substr($0, 1, RLENGTH)
        # Increment count for this index
        count[idx]++
        # Store the first occurrence of the line for this index
        if (!(idx in first_line)) {
            first_line[idx] = $0
        }
    }
}
# Print summary for each line in real-time
match($0, /^[^:]+:/) {
    # Print the first line for this index with count
    printf "%s[%d]\n", first_line[idx], count[idx]
    # Flush output for real-time display
    fflush()
}
' -
