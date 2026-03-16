# EPUB RAG MCP Server - Deployment Guide

This guide shows you how to deploy your EPUB RAG MCP Server to a remote server on your local network.

## Overview

- **Code**: Git repository on GitHub (private)
- **Data (ChromaDB)**: Stored in `data/chroma_db/` - sync separately
- **EPUB Files**: Keep locally, sync to server when needed

---

## Part 1: Setup Git Repository (Local)

### Step 1: Initialize Git

```bash
cd /home/sreeram/Projects/BookRAG
./setup_git_repo.sh
```

This script will:
- Initialize git if needed
- Create `.gitignore` (excludes `.env`, `data/chroma_db/`, `venv/`, etc.)
- Commit all files
- Create a private GitHub repository
- Push to GitHub

**OR manually:**

```bash
# Initialize git
git init

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
venv/
.env
.env.local

# Data
data/chroma_db/

# IDE
.vscode/
.idea/

# Logs
*.log
EOF

# Add and commit
git add .
git commit -m "Initial commit: EPUB RAG MCP Server"

# Create GitHub repo (go to github.com and create a private repo)
# Then add remote and push:
git remote add origin https://github.com/YOUR_USERNAME/epub-rag-mcp.git
git push -u origin main
```

---

## Part 2: Deploy to Server

### Step 1: SSH to Your Server

```bash
ssh user@your-server-ip
# Replace with your actual server IP address
```

### Step 2: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/epub-rag-mcp.git
cd epub-rag-mcp
```

### Step 3: Run Server Setup Script

```bash
./server_setup.sh
```

This script will:
- Check Python version (3.9+ required)
- Create virtual environment
- Install dependencies
- Create `.env` file with your API key
- Launch MCP server to verify it works

### Step 4: Verify Server Runs

The server should start and show:
```
All components initialized successfully
Starting EPUB RAG MCP Server...
Use MCP tools to load and query EPUB files
```

Press `Ctrl+C` to stop (server is running in stdio mode for Opencode).

---

## Part 3: Configure Opencode for Remote Access

### Option A: Direct Path (Server on Local Network)

Add this to Opencode's config file (e.g., `~/.claude.json` or Opencode settings):

```json
{
  "numStartups": 100,
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "ssh",
      "args": ["-t", "user@your-server-ip", "/home/sreeram/epub-rag-mcp/venv/bin/python", "/home/sreeram/epub-rag-mcp/server.py"]
    }
  },
  "autoUpdates": false
}
```

Replace `user@your-server-ip` with your actual server credentials.

### Option B: SSH Tunneling (More Secure)

1. Create SSH tunnel from your local machine:
```bash
ssh -L 8000:localhost:8000 user@your-server-ip -N
```

2. Update your Opencode config:
```json
{
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "ssh",
      "args": ["-o", "ExitOnForwardFailure=yes", "-L", "8000:localhost:8000", "user@localhost", "/home/sreeram/epub-rag-mcp/venv/bin/python", "/home/sreeram/epub-rag-mcp/server.py"]
    }
  }
}
```

### Option C: Run as Service on Server (Background)

On your server, create a systemd service:

```bash
sudo nano /etc/systemd/system/epub-rag-mcp.service
```

```ini
[Unit]
Description=EPUB RAG MCP Server
After=network.target

[Service]
Type=simple
User=sreeram
WorkingDirectory=/home/sreeram/epub-rag-mcp
ExecStart=/home/sreeram/epub-rag-mcp/venv/bin/python /home/sreeram/epub-rag-mcp/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable epub-rag-mcp
sudo systemctl start epub-rag-mcp
sudo systemctl status epub-rag-mcp
```

---

## Part 4: Sync EPUB Files

### On Your Local Machine:

```bash
# Copy new EPUB to server
scp Myst,_Might,_and_Mayhem.epub user@your-server-ip:/home/sreeram/epub-rag-mcp/

# Or use rsync for multiple files
rsync -avz *.epub user@your-server-ip:/home/sreeram/epub-rag-mcp/
```

### On Your Server:

```bash
cd ~/epub-rag-mcp

# Generate embeddings for the new EPUB
python complete_embeddings.py

# Or use test_epub.py for full test
python test_epub.py
```

---

## Part 5: Maintenance

### Update Code on Server

```bash
# On server
cd ~/epub-rag-mcp
git pull
```

### Sync ChromaDB Data

```bash
# From local to server (after generating embeddings)
rsync -avz data/chroma_db/ user@your-server-ip:/home/sreeram/epub-rag-mcp/data/chroma_db/
```

### View Server Logs

```bash
# If running manually
tail -f server.log

# If running as systemd service
sudo journalctl -u epub-rag-mcp -f
```

---

## Troubleshooting

### Error: "OPENROUTER_API_KEY is required"

Make sure `.env` file exists on the server with your API key:
```bash
echo "OPENROUTER_API_KEY=your_key_here" > .env
```

### Error: "EPUB file not found"

Check the file path is correct:
```bash
ls -la /home/sreeram/epub-rag-mcp/
```

### Error: Server starts but crashes

Check the logs:
```bash
python server.py
# Or check systemd logs
sudo journalctl -u epub-rag-mcp -n 50
```

### Connection timeout from Opencode

- Check server is running: `ps aux | grep server.py`
- Check network: `ping your-server-ip`
- Check SSH access: `ssh user@your-server-ip`

---

## Quick Start Summary

**Local Machine:**
```bash
cd /home/sreeram/Projects/BookRAG
./setup_git_repo.sh  # Or manually: git add/commit/push
```

**Server:**
```bash
ssh user@your-server-ip
git clone https://github.com/YOUR_USERNAME/epub-rag-mcp.git
cd epub-rag-mcp
./server_setup.sh
```

**Opencode Config:**
```json
{
  "mcpServers": {
    "epub-rag-mcp": {
      "command": "ssh",
      "args": ["-t", "user@your-server-ip", "/home/sreeram/epub-rag-mcp/venv/bin/python", "/home/sreeram/epub-rag-mcp/server.py"]
    }
  }
}
```

Then restart Opencode!
