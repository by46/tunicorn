#! /bin/sh

COVER=./venv/bin/coverage

./venv/bin/activate

${COVER} run --source sirius -m unittest discover --start-directory test --pattern test_*.py

[ $? -gt 0 ] && exit 1

${COVER} xml