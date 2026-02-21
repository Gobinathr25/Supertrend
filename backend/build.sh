#!/bin/bash
set -e
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Removing broken asyncio PyPI package (shadows built-in)..."
pip uninstall asyncio -y || true

echo "Build complete."
