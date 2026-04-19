#!/bin/bash
# Sync script for ChapterKey
# Usage: ./sync_to_server.sh

set -e

SERVER="user@your-server"
REMOTE_PATH="~/chapterkey"

echo "Syncing ChapterKey to server..."

# Sync EPUB files
echo "Syncing EPUB files..."
rsync -avz --include="*.epub" --exclude="*" /home/sreeram/Projects/BookRAG/ $SERVER:$REMOTE_PATH/

# Sync config
echo "Syncing config..."
rsync -avz .env.template $SERVER:$REMOTE_PATH/

# Sync ChromaDB data (vector embeddings)
echo "Syncing ChromaDB data..."
rsync -avz data/chroma_db/ $SERVER:$REMOTE_PATH/data/chroma_db/

echo "Sync complete!"
echo ""
echo "On server, run:"
echo "  cd $REMOTE_PATH"
echo "  source venv/bin/activate"
echo "  python server.py"
