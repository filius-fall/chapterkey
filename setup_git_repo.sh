#!/bin/bash
# Script to initialize git, commit changes, create private repo, and push
# Usage: ./setup_git_repo.sh

set -e

echo "=== EPUB RAG MCP Server - Git Setup ==="
echo ""

# Configuration
REPO_NAME="epub-rag-mcp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Step 1: Check current git status${NC}"
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "  Git repo already exists"
else
    echo "  Initializing git repository..."
    git init
fi

echo ""
echo -e "${GREEN}Step 2: Create .gitignore${NC}"

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.env
.env.local

# Data (keep .env.template)
data/chroma_db/
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Project specific
*.epub  # EPUB files are large - keep them local or sync separately
Myst,_Might,_and_Mayhem.epub  # Example EPUB - user specific
EOF

echo "  Created .gitignore"

echo ""
echo -e "${GREEN}Step 3: Add all files${NC}"
git add .

echo ""
echo -e "${GREEN}Step 4: Check what will be committed${NC}"
git status

echo ""
echo -e "${YELLOW}IMPORTANT: Before commit, check these files:${NC})"
echo "  - .env: Contains your API key (WIll be auto-ignored by .gitignore)"
echo "  - data/chroma_db/: Vector database (105MB) - will be ignored"
echo "  - *.epub files - ignored (user-specific)"
echo ""

read -p "Press Enter to continue after reviewing..."

echo ""
echo -e "${GREEN}Step 5: Commit changes${NC}"
git commit -m "Initial commit: EPUB RAG MCP Server with OpenRouter integration"

echo ""
echo -e "${GREEN}Step 6: Create private GitHub repository${NC}"

# Create private repo using GitHub CLI
echo "Creating private repo: $REPO_NAME"
gh repo create "$REPO_NAME" --private

# Set remote to SSH and push
echo ""
echo "Setting up SSH remote and pushing..."
git remote set-url origin "git@github.com:filius-fall/$REPO_NAME.git" 2>/dev/null || \
    git remote add origin "git@github.com:filius-fall/$REPO_NAME.git"
git push origin master:main

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Remote repo: https://github.com/filius-fall/$REPO_NAME"
echo "SSH URL: git@github.com:filius-fall/$REPO_NAME.git"
echo ""
echo -e "${YELLOW}Next steps on your server:${NC}"
cat << 'EOF'
1. SSH to your server:
   ssh user@your-server-ip

2. Ensure SSH key is on server (gh auth login on server)
   OR clone with HTTPS: git clone https://github.com/filius-fall/epub-rag-mcp.git

3. Set up the environment:
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .

4. Create .env file with your OpenRouter API key:
   echo "OPENROUTER_API_KEY=your_key_here" > .env

5. Start the server:
   python server.py

6. Access from your local machine:
   - Get server IP: hostname -I
   - Add to Opencode config with SSH tunneling
EOF
