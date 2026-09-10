#!/bin/sh
# Fetch any Iconify icon as SVG into assets/icons/.  Usage: ./get-icon.sh logos:claude-icon [more...]
# Browse/search: https://icon-sets.iconify.design  or  curl 'https://api.iconify.design/search?query=...'
cd "$(dirname "$0")/assets/icons" || exit 1
for spec in "$@"; do
  p=${spec%%:*}; n=${spec##*:}
  curl -sfL "https://api.iconify.design/$p/$n.svg" -o "$p--$n.svg" \
    && echo "ok  $p--$n.svg" || echo "FAIL $spec"
done
