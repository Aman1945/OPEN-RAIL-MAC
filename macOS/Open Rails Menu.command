#!/bin/bash
# Double-click to open the Open Rails menu (it opens in your web browser).
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found. Install the Xcode Command Line Tools with:  xcode-select --install"
    read -n 1 -s -r -p "Press any key to close..."
    exit 1
fi

exec python3 "orts-menu.py"
