#!/bin/sh
set -e

# Start Ollama server in the background
ollama serve &

# Short pause to ensure the server is up
sleep 3

# Download models you want preloaded
# (Add more models below if needed)
echo "Pulling models..."
ollama pull phi4 || true

echo "All models pulled. Ollama is ready."

# Keep the server process alive
wait
