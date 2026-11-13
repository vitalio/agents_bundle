#!/usr/bin/env sh
# Usage: install.sh [-h|--help] [--name CMD] [--dir DIR] [--yes]
#
# Installs or updates agents_bundle (https://github.com/vitalio/agents_bundle).
# Checks for command name conflicts in PATH, offers an alternative name if
# 'agents_bundle' is already taken by another program, installs into ~/.local/bin
# (or --dir).
# -h / --help prints this usage and exits 0 doing nothing.
set -eu

REPO_MARKER="agents_bundle-repo: vitalio/agents_bundle"
RAW_URL="${AGENTS_BUNDLE_UPDATE_URL:-https://raw.githubusercontent.com/vitalio/agents_bundle/main/agents_bundle}"
CMD_NAME="${AGENTS_BUNDLE_NAME:-}"
INSTALL_DIR="${AGENTS_BUNDLE_INSTALL_DIR:-}"
ASSUME_YES=0

usage() {
    sed -n '2,8s/^# \?//p' "$0"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --name)
            if [ "$#" -lt 2 ]; then
                echo "install.sh: --name requires an argument" >&2
                exit 2
            fi
            CMD_NAME="$2"
            shift 2
            ;;
        --dir)
            if [ "$#" -lt 2 ]; then
                echo "install.sh: --dir requires an argument" >&2
                exit 2
            fi
            INSTALL_DIR="$2"
            shift 2
            ;;
        -y|--yes)
            ASSUME_YES=1
            shift
            ;;
        *)
            echo "install.sh: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required but was not found in PATH." >&2
    exit 1
fi
if ! command -v bash >/dev/null 2>&1; then
    echo "Error: bash is required but was not found in PATH." >&2
    exit 1
fi

is_our_binary() {
    [ -f "$1" ] && grep -q "$REPO_MARKER" "$1" 2>/dev/null
}

if [ -z "$CMD_NAME" ]; then
    CMD_NAME="agents_bundle"
    EXISTING="$(command -v "$CMD_NAME" 2>/dev/null || true)"
    if [ -n "$EXISTING" ] && ! is_our_binary "$EXISTING"; then
        echo "Notice: '$CMD_NAME' already exists at $EXISTING (another program)." >&2
        ALT_NAME="agents_bundle_cli"
        if [ "$ASSUME_YES" -eq 0 ] && [ -r /dev/tty ] && [ -w /dev/tty ]; then
            printf "Enter an alternative command name [%s]: " "$ALT_NAME" >/dev/tty
            IFS= read -r USER_NAME </dev/tty || USER_NAME=""
            if [ -n "$USER_NAME" ]; then
                CMD_NAME="$USER_NAME"
            else
                CMD_NAME="$ALT_NAME"
            fi
        else
            CMD_NAME="$ALT_NAME"
            echo "Using alternative command name: $CMD_NAME" >&2
        fi
    fi
fi

if [ -z "$INSTALL_DIR" ]; then
    EXISTING_OUR="$(command -v "$CMD_NAME" 2>/dev/null || true)"
    if [ -n "$EXISTING_OUR" ] && is_our_binary "$EXISTING_OUR"; then
        INSTALL_DIR="$(dirname "$EXISTING_OUR")"
    else
        INSTALL_DIR="$HOME/.local/bin"
    fi
fi

mkdir -p "$INSTALL_DIR"
TARGET="$INSTALL_DIR/$CMD_NAME"

TMP_FILE="$(mktemp "${TMPDIR:-/tmp}/agents_bundle_install.XXXXXX")"
cleanup() {
    rm -f "$TMP_FILE"
}
trap cleanup EXIT INT TERM

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" 2>/dev/null && pwd || pwd)"
if [ -z "${AGENTS_BUNDLE_UPDATE_URL:-}" ] && [ -f "$SCRIPT_DIR/agents_bundle" ] && is_our_binary "$SCRIPT_DIR/agents_bundle"; then
    cp "$SCRIPT_DIR/agents_bundle" "$TMP_FILE"
else
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$RAW_URL" -o "$TMP_FILE"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$TMP_FILE" "$RAW_URL"
    else
        python3 -c 'import sys, urllib.request; data = urllib.request.urlopen(sys.argv[1], timeout=15).read(); open(sys.argv[2], "wb").write(data)' "$RAW_URL" "$TMP_FILE"
    fi
fi

if ! is_our_binary "$TMP_FILE"; then
    echo "Error: downloaded file is not a valid vitalio/agents_bundle script." >&2
    exit 1
fi

chmod 0755 "$TMP_FILE"
mv "$TMP_FILE" "$TARGET"

VER="$("$TARGET" --version 2>/dev/null || echo "$CMD_NAME")"
echo "============================================================"
echo "Installed: $VER -> $TARGET"
case ":${PATH:-}:" in
    *":$INSTALL_DIR:"*) ;;
    *)
        RC_FILE=""
        case "${SHELL:-}" in
            */zsh) RC_FILE="$HOME/.zshrc" ;;
            */bash)
                if [ "$(uname -s 2>/dev/null || true)" = "Darwin" ]; then
                    RC_FILE="$HOME/.bash_profile"
                else
                    RC_FILE="$HOME/.bashrc"
                fi
                ;;
            *)
                if [ "$(uname -s 2>/dev/null || true)" = "Darwin" ]; then
                    RC_FILE="$HOME/.zshrc"
                else
                    RC_FILE="$HOME/.bashrc"
                fi
                ;;
        esac
        EXPORT_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""
        if [ -n "$RC_FILE" ] && [ "$INSTALL_DIR" = "$HOME/.local/bin" ]; then
            if [ ! -f "$RC_FILE" ] || ! grep -Fq "$INSTALL_DIR" "$RC_FILE" 2>/dev/null; then
                printf '\n# Added by %s installer\n%s\n' "$CMD_NAME" "$EXPORT_LINE" >> "$RC_FILE"
                echo "Added $INSTALL_DIR to PATH in $RC_FILE (run 'source $RC_FILE' or open a new terminal)."
            else
                echo "Note: $INSTALL_DIR is in $RC_FILE; run 'source $RC_FILE' or open a new terminal."
            fi
        else
            echo "Note: $INSTALL_DIR is not in your PATH. Add: $EXPORT_LINE"
        fi
        ;;
esac
echo "Tip: run '$CMD_NAME --init-start' and '$CMD_NAME --start' in any repo to build a session context bundle."
echo "============================================================"
