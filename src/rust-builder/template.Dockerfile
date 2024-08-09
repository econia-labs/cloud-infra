# Chainguard image digest (SHA-256), Rust builder version.
ARG DIGEST=5567380ef73d947c834960aa127784eef821c69596366dd48caf77736e854bc2
ARG BUILDER_VERSION=1.0.0

FROM econialabs/rust-builder:$BUILDER_VERSION AS base
WORKDIR /app

FROM base AS planner
ARG BIN
COPY . .
RUN cargo chef prepare --bin "$BIN"

FROM base AS builder
ARG BIN PACKAGE
COPY --from=planner app/recipe.json recipe.json
RUN cargo chef cook --bin "$BIN" --locked --package "$PACKAGE" --release
COPY . .
RUN cargo build --bin "$BIN" --frozen --package "$PACKAGE" --release; \
    mv "/app/target/release/$BIN" /executable;

FROM chainguard/glibc-dynamic@sha256:$DIGEST
COPY --chown=nonroot:nonroot --from=builder /executable /executable
ENTRYPOINT ["/executable"]
