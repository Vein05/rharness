#!/bin/sh
# Build a release tarball from git, write SHA256SUMS, and publish both as GitHub release assets.
# Usage: scripts/release.sh            (uses VERSION)
set -eu
cd "$(dirname "$0")/.."
VERSION=$(cat VERSION)
TAG="v$VERSION"
NAME="rharness-$VERSION"
mkdir -p dist
git archive --format=tar.gz --prefix="$NAME/" -o "dist/$NAME.tar.gz" HEAD
( cd dist && { command -v sha256sum >/dev/null 2>&1 && sha256sum "$NAME.tar.gz" || shasum -a 256 "$NAME.tar.gz"; } > SHA256SUMS )
cat dist/SHA256SUMS
git tag -a "$TAG" -m "rharness $VERSION" 2>/dev/null || echo "tag $TAG exists"
git push -q origin "$TAG"
gh release create "$TAG" "dist/$NAME.tar.gz" dist/SHA256SUMS --title "rharness $VERSION" --notes "See README.md and docs/. Verify with SHA256SUMS." \
  || gh release upload "$TAG" "dist/$NAME.tar.gz" dist/SHA256SUMS --clobber
echo "released $TAG"
