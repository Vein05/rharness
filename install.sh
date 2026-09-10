#!/bin/sh
# rharness installer. Usage: curl -fsSL https://raw.githubusercontent.com/Vein05/rharness/main/install.sh | sh
set -eu

REPO="Vein05/rharness"
HOME_DIR="${RHARNESS_HOME:-$HOME/.rharness}"
STORE="$HOME_DIR/store"

need() { command -v "$1" >/dev/null 2>&1 || { echo "rharness: $1 is required" >&2; exit 2; }; }
need tar
need python3
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "rharness: python3 >= 3.9 required" >&2; exit 2; }

if [ -n "${RHARNESS_VERSION:-}" ]; then
  VERSION="$RHARNESS_VERSION"
else
  need curl
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$VERSION" ] || { echo "rharness: could not resolve latest release" >&2; exit 2; }
fi

mkdir -p "$STORE" "$HOME_DIR/bin"
DEST="$STORE/$VERSION"
if [ ! -d "$DEST" ]; then
  TMP=$(mktemp -d)
  if [ -n "${RHARNESS_TARBALL:-}" ]; then
    cp "$RHARNESS_TARBALL" "$TMP/r.tar.gz"
  else
    need curl
    curl -fsSL "https://github.com/$REPO/archive/refs/tags/$VERSION.tar.gz" -o "$TMP/r.tar.gz"
  fi
  mkdir -p "$TMP/x"
  tar -xzf "$TMP/r.tar.gz" -C "$TMP/x"
  INNER=$(find "$TMP/x" -mindepth 1 -maxdepth 1 -type d | head -1)
  mv "$INNER" "$DEST"
  rm -rf "$TMP"
fi
ln -sfn "$DEST" "$STORE/current"

SHIM="$HOME_DIR/bin/rharness"
cat > "$SHIM" <<EOF
#!/bin/sh
exec python3 "$STORE/current/bin/rharness" "\$@"
EOF
chmod +x "$SHIM"

RC=""
for f in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.profile"; do
  if [ -f "$f" ]; then RC="$f"; break; fi
done
[ -n "$RC" ] || RC="$HOME/.profile"
if ! grep -q "# rharness" "$RC" 2>/dev/null; then
  printf '\n# rharness\nexport PATH="%s/bin:$PATH"\n' "$HOME_DIR" >> "$RC"
fi

echo "rharness $VERSION installed to $DEST"
echo "Open a new shell (or: export PATH=\"$HOME_DIR/bin:\$PATH\"), then:"
echo "  rharness init ~/research"
