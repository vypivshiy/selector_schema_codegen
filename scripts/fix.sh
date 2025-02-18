#!/bin/sh -e

export PREFIX=""
if [ -d '.venv' ] ; then
    export PREFIX=".venv/bin/"
fi
export SOURCE_FILES="ssc_codegen"
export TEST_FILES="tests"

set -x

${PREFIX}ruff format $SOURCE_FILES
${PREFIX}ruff check $SOURCE_FILES --fix
${PREFIX}ruff format $TEST_FILES
${PREFIX}ruff check $TEST_FILES --fix
