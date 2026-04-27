#!/usr/bin/env bash
#
# Download and compile ncurses + zsh from source.
# Builds ncurses as a static library so the zsh binary is self-contained —
# no extra .so files needed, can be copied anywhere.
# Does NOT install — stops after compilation and runs a quick smoke test.
#
# Intended for systems without sudo access — e.g. hardened production containers
# where root/sudo has been dropped for security reasons.  A common use-case is
# dropping a self-contained zsh binary into a stripped-down debug container so
# you get shell conveniences (completion, history, parameter expansion, etc.)
# without needing to install anything system-wide.
#
set -euo pipefail

# ── Argument parsing ──────────────────────────────────────────────────────────
COPY_TO=""
CLEANUP=0

usage() {
    cat >&2 <<'EOF'
Usage: build-zsh.sh [OPTIONS]

Options:
  --copy-to <dest>   scp the finished binary to <dest> (e.g. user@host:/path/to/zsh)
  --cleanup          remove the build directory after a successful build
  -h, --help         show this message
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --copy-to)
            [[ $# -lt 2 ]] && { echo "ERROR: --copy-to requires an argument" >&2; usage; }
            COPY_TO="$2"; shift 2 ;;
        --cleanup)
            CLEANUP=1; shift ;;
        -h|--help)
            usage ;;
        *)
            echo "ERROR: unknown option: $1" >&2; usage ;;
    esac
done

NCURSES_VERSION="6.5"
NCURSES_TARBALL="ncurses-${NCURSES_VERSION}.tar.gz"
NCURSES_URL="https://ftp.gnu.org/gnu/ncurses/${NCURSES_TARBALL}"

ZSH_VERSION_TAG="5.9"
ZSH_TARBALL="zsh-${ZSH_VERSION_TAG}.tar.xz"
ZSH_URL="https://sourceforge.net/projects/zsh/files/zsh/${ZSH_VERSION_TAG}/${ZSH_TARBALL}/download"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/zsh-build.XXXXXX")"
PREFIX="${WORK_DIR}/local"
echo "==> Working directory: ${WORK_DIR}"

cleanup() {
    echo "==> Build artifacts left in ${WORK_DIR}"
}
trap cleanup EXIT

# ═════════════════════════════════════════════════════════════════════════════
# ncurses  (static only — gets linked into zsh)
# ═════════════════════════════════════════════════════════════════════════════

# ── 1a. Download ncurses ─────────────────────────────────────────────────────
echo "==> Downloading ncurses ${NCURSES_VERSION} …"
curl -fSL --retry 3 -o "${WORK_DIR}/${NCURSES_TARBALL}" "${NCURSES_URL}"

# ── 1b. Extract ncurses ─────────────────────────────────────────────────────
echo "==> Extracting ncurses …"
tar xf "${WORK_DIR}/${NCURSES_TARBALL}" -C "${WORK_DIR}"

# ── 1c. Configure ncurses ───────────────────────────────────────────────────
NCURSES_SRC="${WORK_DIR}/ncurses-${NCURSES_VERSION}"
echo "==> Configuring ncurses (static) …"
cd "${NCURSES_SRC}"
CFLAGS="-fPIC" \
./configure --prefix="${PREFIX}" \
            --without-shared \
            --with-normal \
            --enable-widec \
            --without-ada \
            --without-manpages \
            --without-tests

# ── 1d. Compile & install ncurses (locally) ──────────────────────────────────
echo "==> Compiling ncurses ($(nproc) jobs) …"
make -j"$(nproc)"
make install

# convenience symlinks so -lncurses finds ncursesw
for lib in ncurses form panel menu; do
    if [[ -e "${PREFIX}/lib/lib${lib}w.a" ]] && [[ ! -e "${PREFIX}/lib/lib${lib}.a" ]]; then
        ln -s "lib${lib}w.a" "${PREFIX}/lib/lib${lib}.a"
    fi
done
if [[ ! -e "${PREFIX}/include/curses.h" ]] && [[ -e "${PREFIX}/include/ncursesw/curses.h" ]]; then
    ln -s ncursesw/curses.h "${PREFIX}/include/curses.h"
    ln -s ncursesw/ncurses.h "${PREFIX}/include/ncurses.h"
    ln -s ncursesw/term.h "${PREFIX}/include/term.h"
fi

echo "==> ncurses (static) installed to ${PREFIX}"

# ═════════════════════════════════════════════════════════════════════════════
# zsh  (statically linked against ncurses)
# ═════════════════════════════════════════════════════════════════════════════

# ── 2a. Download zsh ─────────────────────────────────────────────────────────
echo "==> Downloading zsh ${ZSH_VERSION_TAG} from SourceForge …"
curl -fSL --retry 3 -o "${WORK_DIR}/${ZSH_TARBALL}" "${ZSH_URL}"

# ── 2b. Extract zsh ─────────────────────────────────────────────────────────
echo "==> Extracting zsh …"
tar xf "${WORK_DIR}/${ZSH_TARBALL}" -C "${WORK_DIR}"

ZSH_SRC="${WORK_DIR}/zsh-${ZSH_VERSION_TAG}"

# ── 2c. Configure zsh (pointing at local static ncurses) ────────────────────
echo "==> Configuring zsh …"
cd "${ZSH_SRC}"
CFLAGS="-I${PREFIX}/include -I${PREFIX}/include/ncursesw" \
LDFLAGS="-L${PREFIX}/lib" \
CPPFLAGS="-I${PREFIX}/include -I${PREFIX}/include/ncursesw" \
./configure --prefix="${WORK_DIR}/install" \
            --enable-multibyte \
            --without-tcsetpgrp \
            --disable-dynamic

# ── 2c½. Force all modules to static ──────────────────────────────────────
# With --disable-dynamic, modules whose .mdd says link=dynamic become link=no
# (disabled) instead of link=static.  Fix that so everything gets compiled in.
# Only convert modules that have load=yes — those were disabled purely because
# --disable-dynamic was set.  Modules with load=no were disabled due to missing
# system dependencies (e.g. gdbm, cap) and must stay link=no.
echo "==> Patching config.modules: forcing link=static for all modules …"
sed -i '/load=yes/s/link=no/link=static/' config.modules

# ── 2d. Compile & install zsh ──────────────────────────────────────────────
echo "==> Compiling zsh ($(nproc) jobs) …"
make -j"$(nproc)"
make install

# ═════════════════════════════════════════════════════════════════════════════
# Smoke tests
# ═════════════════════════════════════════════════════════════════════════════
ZSH_BIN="${WORK_DIR}/install/bin/zsh"

if [[ ! -x "${ZSH_BIN}" ]]; then
    echo "FAIL: zsh binary not found at ${ZSH_BIN}" >&2
    exit 1
fi

echo "==> Smoke-testing the build …"

# verify ncurses is NOT a dynamic dependency
if ldd "${ZSH_BIN}" 2>&1 | grep -qi ncurses; then
    echo "    WARNING: ncurses still appears as a dynamic dependency:"
    ldd "${ZSH_BIN}" | grep -i ncurses | sed 's/^/      /'
else
    echo "    ncurses:    statically linked (not in ldd output)"
fi

# version string
BUILT_VERSION="$("${ZSH_BIN}" --version 2>&1)" || true
echo "    version:    ${BUILT_VERSION}"

# simple expression evaluation
RESULT="$("${ZSH_BIN}" -c 'echo $((6 * 7))')"
if [[ "${RESULT}" == "42" ]]; then
    echo "    math test:  PASS  (6*7 = ${RESULT})"
else
    echo "    math test:  FAIL  (expected 42, got ${RESULT})" >&2
    exit 1
fi

# parameter expansion
RESULT="$("${ZSH_BIN}" -c 's="hello world"; echo ${(U)s}')"
if [[ "${RESULT}" == "HELLO WORLD" ]]; then
    echo "    param test: PASS  (uppercase expansion works)"
else
    echo "    param test: FAIL  (expected 'HELLO WORLD', got '${RESULT}')" >&2
    exit 1
fi

echo ""
echo "==> Build succeeded.  Installed to: ${WORK_DIR}/install"
echo "    Binary:    ${ZSH_BIN}"
echo "    Functions: ${WORK_DIR}/install/share/zsh/${ZSH_VERSION_TAG}/functions"
echo "    To relocate, copy the entire install/ tree together."

if [[ -n "${COPY_TO}" ]]; then
    echo ""
    echo "==> Copying binary to ${COPY_TO} …"
    scp "${ZSH_BIN}" "${COPY_TO}"
    echo "    Done."
fi

if [[ "${CLEANUP}" -eq 1 ]]; then
    echo ""
    echo "==> Cleaning up build directory ${WORK_DIR} …"
    # Disable the EXIT trap so it doesn't print the "artifacts left" message
    trap - EXIT
    rm -rf "${WORK_DIR}"
    echo "    Removed."
fi
