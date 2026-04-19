# Linux Installation

BookRAG is currently packaged for **Debian 12** and **Ubuntu 22.04/24.04** on `amd64`.

The user experience is CLI-first. After install, the main command is:

```bash
bookrag setup
```

By default, setup creates:

```text
~/Documents/BookRAG
~/Documents/BookRAG/input
~/Documents/BookRAG/output
```

## Option 1: Install with pip in a virtualenv

Prerequisites:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

Install:

```bash
python3 -m venv ~/.venvs/bookrag
source ~/.venvs/bookrag/bin/activate
pip install --upgrade pip
pip install bookrag
```

For a local source checkout:

```bash
pip install .
```

Then run:

```bash
bookrag setup
```

## Option 2: Install the Debian package

Install the generated package:

```bash
sudo dpkg -i ./bookrag_<version>_amd64.deb
```

Then run:

```bash
bookrag setup
```

For tagged versions, the `.deb` can also be downloaded from GitHub Releases.

## Building the Debian package

From the repo root:

```bash
./scripts/build_deb.sh
```

This creates:

```text
dist/bookrag_<version>_amd64.deb
```

The package installs:

- `bookrag`
- `bookrag-api`
- `bookrag-mcp`

Runtime configuration sample:

```text
/etc/bookrag/bookrag.env
```

## Docker from the repo

Docker images are not published publicly. If you want Docker, build locally from the repo.

```bash
cp .env.example .env
./scripts/docker_local.sh up
```

Other helper commands:

```bash
./scripts/docker_local.sh build
./scripts/docker_local.sh logs
./scripts/docker_local.sh down
```

## Setup behavior

During `bookrag setup`, the CLI:

1. Offers the default Documents workspace.
2. Lets the user provide a custom workspace root instead.
3. Lets the user keep default `input`/`output` folders or customize them separately.
4. Validates directories before continuing.
5. Asks about deleting originals only for custom input folders.

Deletion rules:

- default managed input: auto-delete after verified conversion
- custom input with delete disabled: never auto-delete
- custom input with delete enabled: ask once more after a verified conversion before deleting the original
