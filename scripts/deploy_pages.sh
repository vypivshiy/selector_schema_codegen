#!/bin/sh -e

BUILD_ONLY=0
NO_PUSH=0

for arg in "$@"; do
    case "$arg" in
        --build-only|-BuildOnly)
            BUILD_ONLY=1
            ;;
        --no-push|-NoPush)
            NO_PUSH=1
            ;;
        *)
            echo "Unknown option: $arg (supported: --build-only, --no-push)" >&2
            exit 1
            ;;
    esac
done

set -x

npm --prefix playground install
npm --prefix playground run build -- --emptyOutDir
: > playground/dist/.nojekyll

if [ "$BUILD_ONLY" -eq 1 ]; then
    echo "Build complete (playground/dist/). Skipping gh-pages update (--build-only)."
    exit 0
fi

if [ "$NO_PUSH" -eq 1 ]; then
    uv run --with ghp-import ghp-import -n -f playground/dist
else
    uv run --with ghp-import ghp-import -n -p -f playground/dist
fi
