# cspell:word nonroot

# Declare base image, used across multiple stages.
FROM econia-labs/muslrust-chef:1.0.0 AS base
WORKDIR /

# Declare minimal workspace layout relative to repository root.
ARG CARGO_WORKSPACE_DIR=src
ARG BIN_NAME=allowlist
ARG BIN_DIR=$CARGO_WORKSPACE_DIR/$BIN_NAME

# Plan build dependencies in a standalone layer.
FROM base AS planner
ARG BIN_DIR BIN_NAME CARGO_WORKSPACE_DIR

# Replicate minimal workspace layout.
COPY $CARGO_WORKSPACE_DIR/Cargo.toml /
COPY $BIN_DIR/Cargo.toml /$BIN_NAME/
COPY $BIN_DIR/src /$BIN_NAME/src

# Prepare build dependency recipe.
RUN cargo chef prepare --bin "$BIN_NAME"

# Start new layer for building binary to avoid invalidating cache when Rust
# source code changes but planner dependencies do not.
FROM base AS builder
ARG BIN_DIR BIN_NAME CARGO_WORKSPACE_DIR

# Copy build dependencies from planner stage, and compile them.
COPY --from=planner /recipe.json /recipe.json
RUN RUST_BACKTRACE=full cargo chef cook --bin "$BIN_NAME" --release

# Replicate minimal workspace layout.
COPY $CARGO_WORKSPACE_DIR/Cargo.toml /
COPY $BIN_DIR/Cargo.toml /$BIN_NAME/
COPY $BIN_DIR/src /$BIN_NAME/src

# Build target binary, in standalone run command so results can be cached.
RUN cargo build --bin "$BIN_NAME" --release;
# Move binary to /executable, strip it, and verify it is statically linked.
RUN ./get-executable.sh "$BIN_NAME"; \
    strip /executable; \
    ./verify-static-build.sh;

# Copy the static binary to a minimal image. Note Chainguard's static image
# only has a latest tag, so the image is not pinned to a specific version
# hadolint ignore=DL3007
FROM chainguard/static:latest AS runtime
ARG BIN_NAME
COPY --chown=nonroot:nonroot --from=builder /executable /executable
ENTRYPOINT ["/executable"]
