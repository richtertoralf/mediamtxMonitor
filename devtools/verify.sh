#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_DIR}"

run_block() {
    local title="$1"
    shift

    printf '\n==> %s\n' "${title}"
    "$@"
}

run_block \
    "Python-Unittests" \
    python3 -m unittest discover -s tests -p 'test_*.py' -v

run_block \
    "Python-Compile- und Syntaxprüfung" \
    python3 -m compileall -q bin tests

run_block \
    "JavaScript-Renderer-Tests" \
    node --test tests/test_renderer.mjs tests/test_systeminfo_renderer.mjs

readonly SHELL_SCRIPTS=(
    install.sh
    uninstall.sh
    mediamtx-monitor
    cli-tools/mediamtx_paths.sh
    cli-tools/showActivePhats_table.sh
    cli-tools/srt-data_table.sh
    devtools/deploy-dev.sh
    devtools/verify.sh
)

run_block "Shell-Syntaxprüfung" bash -n "${SHELL_SCRIPTS[@]}"

if command -v shellcheck >/dev/null 2>&1; then
    run_block "Shellcheck (optional)" shellcheck "${SHELL_SCRIPTS[@]}"
else
    printf '\n==> Shellcheck (optional)\nÜbersprungen: shellcheck ist nicht installiert.\n'
fi

run_block "Git-Whitespace-Prüfung" git diff --check

printf '\nAlle Verifikationsprüfungen erfolgreich.\n'
