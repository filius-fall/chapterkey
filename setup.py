#!/usr/bin/env python3
"""Setup script for the BookRAG application."""

from pathlib import Path

from setuptools import find_packages, setup


readme_file = Path(__file__).parent / "README.md"
requirements_file = Path(__file__).parent / "requirements.txt"

long_description = readme_file.read_text() if readme_file.exists() else ""
requirements = requirements_file.read_text().splitlines() if requirements_file.exists() else []

setup(
    name="bookrag",
    version="2.0.0",
    author="OpenAI Codex",
    description="Self-hosted book RAG application with web UI, REST API, CLI, and MCP bridge",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "bookrag-api=bookrag.api:main",
            "bookrag-cli=bookrag.cli:main",
            "bookrag-mcp=bookrag.mcp_bridge:run",
        ]
    },
    include_package_data=True,
)
