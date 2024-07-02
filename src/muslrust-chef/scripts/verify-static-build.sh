#!/bin/sh
# When ldd is passed a path to a statically linked binary, it prints a message
# to stderr indicating that the binary is statically linked, then exits with an
# error. On arm64 the error message is "not a dynamic executable", while on
# amd64 (x86_64) the error message is "statically linked" (at least as
# observed during multi-platform Docker builds with GitHub actions).
#
# Hence pass the path to the binary at /executable to ldd, redirect stderr to
# stdout, and store the resulting message. Then grep for either of the valid
# messages to check that the binary has been statically linked, and do a
# logical OR of the two grep commands and negate the result. Finally, use the
# result of the negation to determine whether to exit with a nonzero status
# code, causing the build to fail.
MSG="$(ldd executable 2>&1)"
if ! (
	(echo $MSG | grep 'not a dynamic executable') ||
		(echo $MSG | grep 'statically linked')
); then
	echo "failed static build check"
	exit 1
fi
