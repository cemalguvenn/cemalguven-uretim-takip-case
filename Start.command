#!/usr/bin/env bash
# Double-clickable launcher for macOS Finder. Opens a Terminal window and runs
# the project. Equivalent to running ./run.sh from a terminal.
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
./run.sh
echo
echo "Press any key to close this window..."
read -r -n 1
