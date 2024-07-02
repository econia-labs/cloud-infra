#!/bin/sh
# Find executable with provided name, then move it to a predictable location
# (/executable) by removing it from the release directory named after its build
# architecture.
mv "$(find /target/*/release/$1)" /executable
