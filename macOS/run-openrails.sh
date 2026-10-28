#!/bin/bash
# Start Open Rails (native macOS build, Apple Silicon) from the command line, without the menu.
# Usage: ./run-openrails.sh [Open Rails arguments...]
# Example: ./run-openrails.sh -start -explorer "/path/to/ROUTES/Route/PATHS/file.pat" "/path/to/TRAINS/CONSISTS/train.con" 12:00:00 1 0
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/local/share/dotnet:$PATH"
PROGRAM_DIR="$(cd "$(dirname "$0")/Program" && pwd)"
cd "$PROGRAM_DIR"
exec dotnet exec --roll-forward LatestMajor RunActivity.dll "$@"
