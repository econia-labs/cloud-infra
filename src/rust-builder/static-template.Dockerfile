# Chainguard static image tag.
ARG TAG=sha256-67ed8ca8d99e12e8778c038cf88ef7c27d44f08247d317c7135a66ca9d8a7652

# Declare base image and working directory.
FROM econialabs/rust-builder:0.1.0 AS base
WORKDIR /app

# Plan build dependencies in a standalone layer for caching.
FROM base AS planner
ARG MEMBER
COPY . .
RUN cargo chef prepare --bin "$MEMBER"

# In new layer: build dependencies, copy source code, compile executable, then
# prepare it for the next layer.
FROM base AS builder
ARG MEMBER
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --bin "$MEMBER" --release
COPY . .
RUN cargo build --bin "$MEMBER" --release

# RUN ./prepare-executable "$MEMBER" dynamic

# Move binary to /executable, strip it, and verify it is statically linked.
RUN ./get-executable.sh "$MEMBER"; strip /executable; ./verify-static-build.sh;

# Copy static binary to minimal image.
FROM chainguard/static:$TAG
COPY --chown=nonroot:nonroot --from=builder /executable /executable
ENTRYPOINT ["/executable"]