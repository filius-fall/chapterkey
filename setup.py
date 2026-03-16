#!/usr/bin/env python3
"""
Setup script for EPUB RAG MCP Server.

Run: pip install -e .
to install the server in development mode.
"""
from pathlib import Path
from setuptools import setup, find_packages

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = requirements_file.read_text().splitlines() if requirements_file.exists() else []

setup(
    name="epub-rag-mcp",
    version="1.0.0",
    author="Claude Code",
    description="EPUB RAG MCP Server for querying EPUB files using vector embeddings",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/epub-rag-mcp",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "epub-rag-mcp=server:main",
        ],
    },
    include_package_data=True,
    package_data={
        "epub-rag-mcp": ["*.md", "*.txt"],
    },
)
