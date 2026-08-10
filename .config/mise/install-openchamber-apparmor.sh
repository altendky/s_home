#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_NAME="openchamber-appimage"
SOURCE_FILE="$SOURCE_DIR/$PROFILE_NAME.apparmor"
TARGET_FILE="/etc/apparmor.d/$PROFILE_NAME"

if [[ ! -f "$SOURCE_FILE" ]]; then
  printf 'Missing profile source: %s\n' "$SOURCE_FILE" >&2
  exit 1
fi

# Validate syntax before touching the system profile.
apparmor_parser -Q -K "$SOURCE_FILE"

if [[ "$(id -u)" -eq 0 ]]; then
  install -D -m 0644 "$SOURCE_FILE" "$TARGET_FILE"
  apparmor_parser -r "$TARGET_FILE"
else
  sudo install -D -m 0644 "$SOURCE_FILE" "$TARGET_FILE"
  sudo apparmor_parser -r "$TARGET_FILE"
fi

printf 'Installed AppArmor profile: %s\n' "$TARGET_FILE"
printf 'Retry launching with: openchamber\n'
