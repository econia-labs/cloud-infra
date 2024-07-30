# Allowlist

## Design

### Components

`allowlist` combines a Redis in-memory database with an asynchronous REST API.
The server, implemented in Rust, is modeled off a [basic `axum` example] and
adapts features from an [`axum` with Redis example], in particular a
[custom extractor] for a database connection, which is extended in `allowlist`
via a [nested extractor]. The server also implements `CTRL+C` and `SIGTERM`
signal handling, modeled off an [`axum` graceful shutdown example], to comply
with [AWS container best practices].

### Containerization

`allowlist` is containerized via the [template Dockerfile] for [`rust-builder`]
and published to the [`allowlist` Docker Hub image] via [`push-allowlist.yaml`].

## Running a local deployment

From repository root:

```sh
docker compose --file src/allowlist/compose.yaml up
```

Or in detached mode:

```sh
docker compose --file src/allowlist/compose.yaml up --detach
```

To stop from detached mode:

```sh
docker compose --file src/allowlist/compose.yaml down
```

## Querying a local deployment

To run the below commands, you'll need `curl` and `jq` on your machine.

### Check if address is allowed

```sh
REQUESTED_ADDRESS=0x123
curl localhost:3000/$REQUESTED_ADDRESS | jq
```

### Add address to allowlist

```sh
REQUESTED_ADDRESS=0x123
curl localhost:3000/$REQUESTED_ADDRESS -X POST | jq
```

### Observe automatic address sanitation

```sh
REQUESTED_ADDRESS=0x00000123
curl localhost:3000/$REQUESTED_ADDRESS -X POST | jq
```

[aws container best practices]: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-considerations.html
[basic `axum` example]: https://github.com/tokio-rs/axum/tree/main?tab=readme-ov-file#usage-example
[custom extractor]: https://github.com/tokio-rs/axum/blob/035c8a36b591bb81b8d107c701ac4b14c0230da3/examples/tokio-redis/src/main.rs#L75
[nested extractor]: https://docs.rs/axum/0.7.5/axum/extract/index.html#accessing-other-extractors-in-fromrequest-or-fromrequestparts-implementations
[template dockerfile]: ../rust-builder/template.Dockerfile
[`allowlist` docker hub image]: https://hub.docker.com/repository/docker/econialabs/allowlist/tags
[`axum` graceful shutdown example]: https://github.com/tokio-rs/axum/blob/main/examples/graceful-shutdown/src/main.rs
[`axum` with redis example]: https://github.com/tokio-rs/axum/blob/main/examples/tokio-redis/src/main.rs
[`push-allowlist.yaml`]: ../../.github/workflows/push-allowlist.yaml
[`rust-builder`]: ../rust-builder/README.md
