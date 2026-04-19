#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 - <<'PY'
import re
from pathlib import Path
text = Path("setup.py").read_text()
match = re.search(r'version="([^"]+)"', text)
print(match.group(1))
PY
)"
ARCH="${ARCH:-amd64}"
PKG_NAME="bookrag"
BUILD_ROOT="${ROOT_DIR}/dist/deb-build"
STAGE_DIR="${BUILD_ROOT}/${PKG_NAME}_${VERSION}_${ARCH}"
APP_ROOT="/opt/bookrag"
VENV_DIR="${APP_ROOT}/venv"
SRC_DIR="${APP_ROOT}/src"
BOOTSTRAP_LOG="/var/log/bookrag-bootstrap.log"

rm -rf "${STAGE_DIR}"
mkdir -p \
  "${STAGE_DIR}/DEBIAN" \
  "${STAGE_DIR}${APP_ROOT}" \
  "${STAGE_DIR}${SRC_DIR}" \
  "${STAGE_DIR}/usr/bin" \
  "${STAGE_DIR}/usr/share/man/man1" \
  "${STAGE_DIR}/etc/bookrag" \
  "${STAGE_DIR}/var/log"

rsync -a \
  --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  "${ROOT_DIR}/bookrag" "${STAGE_DIR}${SRC_DIR}/"
install -m 0644 "${ROOT_DIR}/setup.py" "${STAGE_DIR}${SRC_DIR}/setup.py"
install -m 0644 "${ROOT_DIR}/requirements.txt" "${STAGE_DIR}${SRC_DIR}/requirements.txt"
install -m 0644 "${ROOT_DIR}/README.md" "${STAGE_DIR}${SRC_DIR}/README.md"
install -m 0644 "${ROOT_DIR}/.env.example" "${STAGE_DIR}${SRC_DIR}/.env.example"
install -m 0644 "${ROOT_DIR}/.env.template" "${STAGE_DIR}${SRC_DIR}/.env.template"
install -m 0644 "${ROOT_DIR}/app_server.py" "${STAGE_DIR}${SRC_DIR}/app_server.py"
install -m 0644 "${ROOT_DIR}/server.py" "${STAGE_DIR}${SRC_DIR}/server.py"

cat > "${STAGE_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: ChapterKey
Depends: python3, python3-venv
Description: ChapterKey CLI-first book retrieval toolkit for EPUB and PDF indexing
 ChapterKey installs a self-contained Python environment and CLI tools for
 ingesting books into a local vector database with spoiler-aware retrieval.
 The package creates its virtual environment on the target machine so Python
 paths and compiled dependencies match the installed system.
EOF

cat > "${STAGE_DIR}/usr/bin/bookrag" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -f /etc/bookrag/bookrag.env ]]; then
  set -a
  source /etc/bookrag/bookrag.env
  set +a
fi
if [[ -f "$HOME/.config/bookrag.env" ]]; then
  set -a
  source "$HOME/.config/bookrag.env"
  set +a
fi
if [[ ! -x /opt/bookrag/venv/bin/bookrag ]]; then
  echo "ChapterKey is not bootstrapped yet. Re-run: sudo dpkg --configure bookrag" >&2
  echo "Bootstrap log: /var/log/bookrag-bootstrap.log" >&2
  exit 1
fi
exec /opt/bookrag/venv/bin/bookrag "$@"
EOF

cat > "${STAGE_DIR}/usr/bin/bookrag-api" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -f /etc/bookrag/bookrag.env ]]; then
  set -a
  source /etc/bookrag/bookrag.env
  set +a
fi
if [[ -f "$HOME/.config/bookrag.env" ]]; then
  set -a
  source "$HOME/.config/bookrag.env"
  set +a
fi
if [[ ! -x /opt/bookrag/venv/bin/bookrag-api ]]; then
  echo "ChapterKey is not bootstrapped yet. Re-run: sudo dpkg --configure bookrag" >&2
  echo "Bootstrap log: /var/log/bookrag-bootstrap.log" >&2
  exit 1
fi
exec /opt/bookrag/venv/bin/bookrag-api "$@"
EOF

cat > "${STAGE_DIR}/usr/bin/bookrag-mcp" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ -f /etc/bookrag/bookrag.env ]]; then
  set -a
  source /etc/bookrag/bookrag.env
  set +a
fi
if [[ -f "$HOME/.config/bookrag.env" ]]; then
  set -a
  source "$HOME/.config/bookrag.env"
  set +a
fi
if [[ ! -x /opt/bookrag/venv/bin/bookrag-mcp ]]; then
  echo "ChapterKey is not bootstrapped yet. Re-run: sudo dpkg --configure bookrag" >&2
  echo "Bootstrap log: /var/log/bookrag-bootstrap.log" >&2
  exit 1
fi
exec /opt/bookrag/venv/bin/bookrag-mcp "$@"
EOF

cat > "${STAGE_DIR}/DEBIAN/postinst" <<EOF
#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT}"
VENV_DIR="${VENV_DIR}"
SRC_DIR="${SRC_DIR}"
BOOTSTRAP_LOG="${BOOTSTRAP_LOG}"

mkdir -p "\$(dirname "\${BOOTSTRAP_LOG}")"
: > "\${BOOTSTRAP_LOG}"
chmod 0644 "\${BOOTSTRAP_LOG}"

log() {
  echo "[postinst] \$*" | tee -a "\${BOOTSTRAP_LOG}"
}

run_bootstrap() {
  log "Creating target-native virtual environment at \${VENV_DIR}"
  rm -rf "\${VENV_DIR}"
  python3 -m venv "\${VENV_DIR}" >> "\${BOOTSTRAP_LOG}" 2>&1
  "\${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel >> "\${BOOTSTRAP_LOG}" 2>&1
  log "Installing ChapterKey from bundled source"
  "\${VENV_DIR}/bin/python" -m pip install "\${SRC_DIR}" >> "\${BOOTSTRAP_LOG}" 2>&1
}

case "\${1:-configure}" in
  configure)
    run_bootstrap
    ;;
esac
EOF

cat > "${STAGE_DIR}/DEBIAN/prerm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

case "${1:-remove}" in
  remove|deconfigure)
    exit 0
    ;;
esac
EOF

chmod 0755 "${STAGE_DIR}/usr/bin/bookrag" "${STAGE_DIR}/usr/bin/bookrag-api" "${STAGE_DIR}/usr/bin/bookrag-mcp"
chmod 0755 "${STAGE_DIR}/DEBIAN/postinst" "${STAGE_DIR}/DEBIAN/prerm"
install -m 0644 "${ROOT_DIR}/packaging/bookrag.env" "${STAGE_DIR}/etc/bookrag/bookrag.env"

if [[ -f "${ROOT_DIR}/packaging/man/bookrag.1" ]]; then
  install -m 0644 "${ROOT_DIR}/packaging/man/bookrag.1" "${STAGE_DIR}/usr/share/man/man1/bookrag.1"
  gzip -f "${STAGE_DIR}/usr/share/man/man1/bookrag.1"
fi

mkdir -p "${ROOT_DIR}/dist"
dpkg-deb --root-owner-group --build "${STAGE_DIR}" "${ROOT_DIR}/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Built package: ${ROOT_DIR}/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
