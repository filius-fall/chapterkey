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
VENV_DIR="/opt/bookrag/venv"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/DEBIAN" "${STAGE_DIR}/opt/bookrag" "${STAGE_DIR}/usr/bin" "${STAGE_DIR}/etc/bookrag"

python3 -m venv "${STAGE_DIR}${VENV_DIR}"
"${STAGE_DIR}${VENV_DIR}/bin/pip" install --upgrade pip
"${STAGE_DIR}${VENV_DIR}/bin/pip" install "${ROOT_DIR}"

cat > "${STAGE_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: BookRAG
Depends: python3, python3-venv
Description: CLI-first book RAG toolkit for EPUB and PDF indexing
 BookRAG installs a self-contained Python environment and CLI tools for
 ingesting books into a local vector database with spoiler-aware retrieval.
EOF

cat > "${STAGE_DIR}/usr/bin/bookrag" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
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
exec /opt/bookrag/venv/bin/bookrag-mcp "$@"
EOF

chmod 0755 "${STAGE_DIR}/usr/bin/bookrag" "${STAGE_DIR}/usr/bin/bookrag-api" "${STAGE_DIR}/usr/bin/bookrag-mcp"
install -m 0644 "${ROOT_DIR}/packaging/bookrag.env" "${STAGE_DIR}/etc/bookrag/bookrag.env"

mkdir -p "${ROOT_DIR}/dist"
dpkg-deb --build "${STAGE_DIR}" "${ROOT_DIR}/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Built package: ${ROOT_DIR}/dist/${PKG_NAME}_${VERSION}_${ARCH}.deb"
