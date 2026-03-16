#!/bin/bash
# Script to set up EPUB RAG MCP Server on a remote server
# Usage: Run this script after cloning the repo on your server

set -e

echo "=== EPUB RAG MCP Server Setup on Server ==="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Step 1: Check Python version${NC}"
python3 --version
if [ $(python3 --version 2>&1 | awk -F'.' '{print $2}') -lt 9 ]; then
    echo -e "${RED}Python 3.9+ required${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 2: Create virtual environment${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created venv"
else
    echo "  venv already exists"
fi

echo ""
echo -e "${GREEN}Step 3: Activate and install dependencies${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -e .

echo ""
echo -e "${GREEN}Step 4: Create .env file${NC}"
if [ ! -f ".env" ]; then
    echo ""
    echo -e "${YELLOW}Please enter your OpenRouter API key:${NC}"
    read -p "OPENROUTER_API_KEY=" API_KEY
    echo "OPENROUTER_API_KEY=$API_KEY" > .env
    echo "EMBEDDING_MODEL=openai/text-embedding-3-small" >> .env
    echo "LLM_MODEL=google/gemini-2.5-flash-preview" >> .env
    echo "CHUNK_SIZE=750" >> .env
    echo "CHUNK_OVERLAP=100" >> .env
    echo "TOP_K=5" >> .env
    echo "  Created .env file"
else
    echo "  .env already exists"
fi

echo ""
echo -e "${GREEN}Step 5: Install uvicorn for HTTP access (optional)${NC}"
pip install uvicorn fastapi

echo ""
echo -e "${GREEN}Step 6: Update MCP config for remote access${NC}"
cat > /tmp/mcp_launch.sh << 'EOF'
#!/bin/bash
cd /home/sreeram/epub-rag-mcp
source /home/sreeram/epub-rag-mcp/venv/bin/activate
exec /home/sreeram/epub-rag-mcp/venv/bin/python /home/sreeram/epub-rag-mcp/server.py
EOF
chmod +x /tmp/mcp_launch.sh

echo "  Created launcher: /tmp/mcp_launch.sh"

echo ""
echo -e "${GREEN}Step 7: Test the server (Ctrl+C to stop)${NC}"
echo "  Server will start in stdio mode for Opencode/Claude Code"
timeout 5 python server.py || true

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "To run the server in the background:"
echo "  nohup python server.py > server.log 2>&1 &"
echo ""
echo "To check logs:"
echo "  tail -f server.log"
echo ""
echo "To access from your local machine (same network):"
echo "  1. Get server IP: hostname -I"
echo "  2. Add to Opencode config:"
echo ""
cat << 'EOF'
{
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "/bin/bash",
      "args": ["/home/sreeram/epub-rag-mcp/venv/bin/python", "/home/sreeram/epub-rag-mcp/server.py"]
    }
  }
}
EOF
echo ""
echo "Or use SSH tunneling for remote access"
echo "  ssh -L 8000:localhost:8000 user@server-ip"
