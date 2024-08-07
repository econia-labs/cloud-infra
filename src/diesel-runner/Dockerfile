FROM rust:slim-bookworm

RUN apt-get update && apt-get install -y \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install diesel_cli \
    --features postgres \
    --no-default-features