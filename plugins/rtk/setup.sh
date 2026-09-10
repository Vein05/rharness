#!/bin/sh
# Install rtk if missing. Never fails the plugin install; prints what to do.
if command -v rtk >/dev/null 2>&1; then
  echo "rtk $(rtk --version 2>/dev/null | head -1) already installed"
else
  if command -v brew >/dev/null 2>&1; then
    echo "Installing rtk via Homebrew..."
    brew install rtk-ai/tap/rtk 2>/dev/null || brew install rtk || true
  elif command -v cargo >/dev/null 2>&1; then
    echo "Installing rtk via cargo..."
    cargo install rtk || true
  fi
  if command -v rtk >/dev/null 2>&1; then
    echo "rtk installed"
  else
    echo "rtk not installed automatically. See https://github.com/rtk-ai/rtk#installation, then rerun: rharness doctor"
  fi
fi
command -v jq >/dev/null 2>&1 || echo "jq is required by the hook: brew install jq (or apt install jq)"
exit 0
