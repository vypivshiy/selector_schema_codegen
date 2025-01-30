#!/bin/sh -e

export PREFIX=""
if [ -d '.venv' ] ; then
    export PREFIX=".venv/bin/"
fi
export SOURCE_FILES="ssc_codegen"

set -x

${PREFIX}ruff format $SOURCE_FILES
${PREFIX}ruff check $SOURCE_FILES --select I --fix