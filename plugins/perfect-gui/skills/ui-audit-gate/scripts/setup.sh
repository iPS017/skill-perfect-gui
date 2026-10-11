#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="${UI_AUDIT_CACHE:-$HOME/.cache/ui-audit-gate}"
VENV_DIR="${UI_AUDIT_VENV:-$CACHE_DIR/venv}"
AXE_VERSION="4.10.2"
WITH_BROWSERS=0
WITH_AXE=1

for arg in "$@"; do
  case "$arg" in
    --with-browsers) WITH_BROWSERS=1 ;;
    --no-axe) WITH_AXE=0 ;;
    *) echo "Option inconnue : $arg (options : --with-browsers, --no-axe)" >&2; exit 2 ;;
  esac
done

PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
  echo "Python 3 introuvable. Installer Python 3.9 ou plus récent." >&2
  exit 3
fi

mkdir -p "$CACHE_DIR"
if [ ! -x "$VENV_DIR/bin/python" ] && [ ! -x "$VENV_DIR/Scripts/python.exe" ]; then
  echo "Création du venv : $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi
VENV_PY="$VENV_DIR/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="$VENV_DIR/Scripts/python.exe"

"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet "playwright>=1.49" "pillow>=10"

has_system_browser=0
for candidate in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge msedge; do
  if command -v "$candidate" >/dev/null 2>&1; then has_system_browser=1; break; fi
done
if [ "$(uname)" = "Darwin" ] && [ -d "/Applications/Google Chrome.app" ]; then has_system_browser=1; fi

if [ "$WITH_BROWSERS" = 1 ]; then
  "$VENV_PY" -m playwright install chromium firefox webkit
elif [ "$has_system_browser" = 0 ]; then
  echo "Aucun Chrome ou Edge système détecté : installation de Chromium pour Playwright."
  "$VENV_PY" -m playwright install chromium
fi

if [ "$WITH_AXE" = 1 ] && [ ! -f "$CACHE_DIR/axe-$AXE_VERSION.min.js" ]; then
  for url in "https://cdnjs.cloudflare.com/ajax/libs/axe-core/$AXE_VERSION/axe.min.js" "https://cdn.jsdelivr.net/npm/axe-core@$AXE_VERSION/axe.min.js"; do
    if "$VENV_PY" -c "import sys, urllib.request; open(sys.argv[2], 'wb').write(urllib.request.urlopen(sys.argv[1], timeout=30).read())" "$url" "$CACHE_DIR/axe-$AXE_VERSION.min.js"; then
      break
    fi
  done
fi

echo "Prêt. Venv : $VENV_DIR"
"$VENV_PY" -c "import playwright, PIL; print('playwright', getattr(playwright, '__version__', '?'), '| pillow', PIL.__version__)"
