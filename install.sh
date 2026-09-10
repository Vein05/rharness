#!/bin/sh
# rharness installer. Usage: curl -fsSL https://raw.githubusercontent.com/Vein05/rharness/main/install.sh | sh
# Downloads the release tarball and its SHA256SUMS from GitHub Releases and refuses to install on a mismatch.
set -eu

REPO="Vein05/rharness"
HOME_DIR="${RHARNESS_HOME:-$HOME/.rharness}"
STORE="$HOME_DIR/store"

need() { command -v "$1" >/dev/null 2>&1 || { echo "rharness: $1 is required" >&2; exit 2; }; }
need tar
need python3
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
  || { echo "rharness: python3 >= 3.9 required" >&2; exit 2; }

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; fi
}

if [ -n "${RHARNESS_VERSION:-}" ]; then
  VERSION="$RHARNESS_VERSION"
else
  need curl
  VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$VERSION" ] || { echo "rharness: could not resolve latest release" >&2; exit 2; }
fi
PLAIN="${VERSION#v}"
ASSET="rharness-$PLAIN.tar.gz"

mkdir -p "$STORE" "$HOME_DIR/bin"
DEST="$STORE/$VERSION"
if [ ! -d "$DEST" ]; then
  TMP=$(mktemp -d)
  if [ -n "${RHARNESS_TARBALL:-}" ]; then
    cp "$RHARNESS_TARBALL" "$TMP/$ASSET"
    SUMS="${RHARNESS_SUMS:-$(dirname "$RHARNESS_TARBALL")/SHA256SUMS}"
    [ -f "$SUMS" ] && cp "$SUMS" "$TMP/SHA256SUMS" || true
  else
    need curl
    BASE="https://github.com/$REPO/releases/download/$VERSION"
    curl -fsSL "$BASE/$ASSET" -o "$TMP/$ASSET"
    curl -fsSL "$BASE/SHA256SUMS" -o "$TMP/SHA256SUMS" || true
  fi
  if [ -f "$TMP/SHA256SUMS" ]; then
    EXPECTED=$(grep " \*\{0,1\}$ASSET\$" "$TMP/SHA256SUMS" | head -1 | cut -d' ' -f1)
    ACTUAL=$(sha256_of "$TMP/$ASSET")
    if [ -z "$EXPECTED" ] || [ "$EXPECTED" != "$ACTUAL" ]; then
      echo "rharness: checksum mismatch for $ASSET" >&2
      echo "  expected: ${EXPECTED:-<not listed in SHA256SUMS>}" >&2
      echo "  actual:   $ACTUAL" >&2
      rm -rf "$TMP"
      exit 3
    fi
    echo "verified $ASSET sha256 $ACTUAL"
  elif [ "${RHARNESS_INSECURE:-}" != "1" ]; then
    echo "rharness: no SHA256SUMS available for $VERSION; refusing to install unverified. Set RHARNESS_INSECURE=1 to override." >&2
    rm -rf "$TMP"
    exit 3
  fi
  mkdir -p "$TMP/x"
  tar -xzf "$TMP/$ASSET" -C "$TMP/x"
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
