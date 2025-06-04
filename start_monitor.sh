#!/bin/bash
set -e

echo "Starting Network Intelligence Monitor..."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Run setup first."
    exit 1
fi

# Set environment variables
export PYTHONPATH="$(pwd)"
export DEPLOYMENT_TYPE="${DEPLOYMENT_TYPE:-standard}"

# Start the monitor
python -m src.main "$@"
