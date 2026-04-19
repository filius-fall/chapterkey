"""Ollama installation, startup, and model management helpers."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

OLLAMA_API_BASE = "http://127.0.0.1:11434"


def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def is_ollama_running(timeout: float = 3.0) -> bool:
    try:
        response = requests.get(f"{OLLAMA_API_BASE}/api/tags", timeout=timeout)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def install_ollama() -> bool:
    if is_ollama_installed():
        return True
    print("Installing Ollama via official install script...")
    try:
        result = subprocess.run(
            ["curl", "-fsSL", "https://ollama.com/install.sh"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"Failed to download Ollama install script: {result.stderr}")
            return False
        install_result = subprocess.run(
            ["sh"],
            input=result.stdout,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if install_result.returncode != 0:
            if "Permission denied" in install_result.stderr or "root" in install_result.stderr.lower():
                print("Ollama install requires elevated permissions. Retrying with sudo...")
                install_result = subprocess.run(
                    ["sudo", "sh"],
                    input=result.stdout,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=300,
                )
            if install_result.returncode != 0:
                print(f"Failed to install Ollama: {install_result.stderr}")
                return False
        if not is_ollama_installed():
            print("Ollama installation completed but binary not found in PATH.")
            return False
        print("Ollama installed successfully.")
        return True
    except subprocess.TimeoutExpired:
        print("Ollama installation timed out.")
        return False
    except Exception as exc:
        print(f"Ollama installation failed: {exc}")
        return False


def start_ollama_background() -> subprocess.Popen[bytes] | None:
    if is_ollama_running():
        return None
    if not is_ollama_installed():
        return None
    try:
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(30):
            time.sleep(0.5)
            if is_ollama_running():
                print("Ollama server started.")
                return process
        print("Ollama server did not start within 15 seconds.")
        return None
    except Exception as exc:
        print(f"Failed to start Ollama server: {exc}")
        return None


def list_pulled_models() -> list[str]:
    if not is_ollama_installed():
        return []
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            return []
        models: list[str] = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def is_model_pulled(model: str) -> bool:
    pulled = list_pulled_models()
    return any(p == model or p.startswith(model.split(":")[0]) for p in pulled)


def pull_model(model: str) -> bool:
    if not is_ollama_installed():
        return False
    if not is_ollama_running():
        start_ollama_background()
    print(f"Pulling model '{model}' (this may take a while)...")
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            text=True,
            check=False,
            timeout=1800,
        )
        if result.returncode != 0:
            print(f"Failed to pull model '{model}'.")
            return False
        print(f"Model '{model}' pulled successfully.")
        return True
    except subprocess.TimeoutExpired:
        print(f"Pulling model '{model}' timed out after 30 minutes.")
        return False
    except Exception as exc:
        print(f"Failed to pull model '{model}': {exc}")
        return False


def ensure_ollama_ready(
    *,
    models: list[str] | None = None,
    auto_install: bool = True,
    auto_start: bool = True,
    auto_pull: bool = True,
) -> dict[str, Any]:
    """Ensure Ollama is installed, running, and models are pulled.

    Returns a status dict with keys: installed, running, models_pulled, models_requested.
    """
    status: dict[str, Any] = {
        "installed": is_ollama_installed(),
        "running": False,
        "models_pulled": [],
        "models_requested": models or [],
    }

    if not status["installed"]:
        if not auto_install:
            return status
        if not install_ollama():
            return status
        status["installed"] = True

    if not is_ollama_running():
        if auto_start:
            start_ollama_background()
        status["running"] = is_ollama_running()
    else:
        status["running"] = True

    if models and status["running"]:
        for model in models:
            if is_model_pulled(model):
                status["models_pulled"].append(model)
                continue
            if auto_pull:
                if pull_model(model):
                    status["models_pulled"].append(model)

    return status
