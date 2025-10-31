#!/bin/bash
# Helper script to run the scraper with the virtual environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# If we're in code/ directory, go up one level to project root
if [ "$(basename "$SCRIPT_DIR")" = "code" ]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    cd "$PROJECT_ROOT"
else
    PROJECT_ROOT="$SCRIPT_DIR"
    cd "$PROJECT_ROOT"
fi

# Check if venv exists (should be in project root)
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found!"
    echo "Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv and run scraper from code/ directory
source venv/bin/activate
cd "$PROJECT_ROOT/code"
python scraper.py "$@"

