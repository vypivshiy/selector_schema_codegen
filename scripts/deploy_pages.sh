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

uv run --group docs mkdocs build --clean
npm --prefix playground install
npm --prefix playground run build -- --outDir ../site/playground --emptyOutDir

if [ "$BUILD_ONLY" -eq 1 ]; then
    echo "Build complete (site/ and site/playground/). Skipping gh-pages update (--build-only)."
    exit 0
fi

if [ "$NO_PUSH" -eq 1 ]; then
    uv run --group docs ghp-import -n -f site
else
    uv run --group docs ghp-import -n -p -f site
fi
