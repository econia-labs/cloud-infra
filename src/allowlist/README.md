<!--
cspell:word mimalloc
cspell:word sadd
cspell:word sismember
cspell:word smembers
-->

# Allowlist

## Design

### Components

`allowlist` combines a Redis in-memory database with an asynchronous REST API.
The server, implemented in Rust, is modeled off a [basic `axum` example] and
adapts features from an [`axum` with Redis example], in particular a
[custom extractor] for a database connection, which is extended in `allowlist`
via a [nested extractor].

### Containerization

To simplify container layout, `allowlist` is compiled to a static binary using
the `musl` C library and a multi-stage Docker build. Notably, for Rust
applications without any non-Rust dependencies, this approach enables the
compilation of a standalone executable such that the resulting Docker image is
only as large as the target Rust binary itself. For relevant blog posts on this
topic, see [here][how to create small docker images for rust],
[here][how to package rust applications into minimal docker containers],
[here][use multi-stage docker builds for statically-linked rust binaries], and
[here][docker "from scratch" for rust applications]. For forum discussions, see
[here][looking for the perfect dockerfile for rust],
[here][how to generate statically linked executables?], and
[here][rust linker fails when using target-feature=+crt-static on nightly]. For
relevant Rust documentation see [here][static and dynamic c runtimes] and
[here][`target-feature`].

The `allowlist` binary leverages the [`mimalloc` crate] as a drop-in
[global allocator] solution, which is required to prevent asynchronous
performance regression when statically compiling against `musl`, as detailed
[here][supercharging your rust static executables with mimalloc],
[here][testing alternative c memory allocators pt 2: the musl mystery], and
[here][static linking for rust without glibc - scratch image]. Notably, this
approach eliminates the requirement of a Docker build image with a
manually-patched allocator, as proposed [here][`rust-alpine-mimalloc`],
[here][`mimalloc`], and [here][`alpine-mimalloc`].

Static containerization is performed via the [`muslrust`] image due to its
extensive instructive documentation (in particular its examples and
[`mimalloc` commentary]), though notably there are several other comparable
solutions including [`rust-musl-builder`], which contains a useful index of
associated projects.  Cross-compilation to the `x86_64-unknown-linux-musl`
target architecture is *not* performed in the `allowlist` Dockerfile, so as to
enable local builds with the Docker compose environment. For more on
cross-compilation, see [here][building x86 rust containers from mac silicon],
[here][cross-compiling static rust binaries in docker for raspberry pi], and
[here][`rust-static-builder`].

Per [`muslrust`] best practice recommendations, [`cargo-chef`] is used for image
layer caching, and the final executable is stored in a [`chainguard/static`]
base image (rather than `scratch`) as additionally recommended
[here][`kube.rs` best practices]. This approach yields a final Docker image that
is only 2.5 MB when compiled on an `arm64` machine.

### Deployment automation

`allowlist` is cross-compiled into a [multi-platform image] and uses
[layer caching on GitHub Actions]. Since [`muslrust`] only provides `arm64` and
`amd64` base images, `allowlist` is only compiled for these two architectures.

## Running a local deployment

```sh
docker compose up
```

Or in detached mode:

```sh
docker compose --detach
```

To stop from detached mode:

```sh
docker compose down
```

## Check if address is allowed

```sh
REQUESTED_ADDRESS=0x123
curl localhost:3000/$REQUESTED_ADDRESS | jq
```

## Add address to allowlist

```sh
REQUESTED_ADDRESS=0x123
curl localhost:3000/$REQUESTED_ADDRESS -X POST | jq
```

[basic `axum` example]: https://github.com/tokio-rs/axum/tree/main?tab=readme-ov-file#usage-example
[building x86 rust containers from mac silicon]: https://loige.co/building_x86_rust-containers-from-mac-silicon/
[cross-compiling static rust binaries in docker for raspberry pi]: https://jakewharton.com/cross-compiling-static-rust-binaries-in-docker-for-raspberry-pi/
[custom extractor]: https://github.com/tokio-rs/axum/blob/035c8a36b591bb81b8d107c701ac4b14c0230da3/examples/tokio-redis/src/main.rs#L75
[docker "from scratch" for rust applications]: https://www.21analytics.ch/blog/docker-from-scratch-for-rust-applications/
[global allocator]: https://doc.rust-lang.org/std/alloc/index.html#the-global_allocator-attribute
[how to create small docker images for rust]: https://kerkour.com/rust-small-docker-image
[how to generate statically linked executables?]: https://stackoverflow.com/a/31778003
[how to package rust applications into minimal docker containers]: https://alexbrand.dev/post/how-to-package-rust-applications-into-minimal-docker-containers/
[layer caching on github actions]: https://docs.docker.com/build/ci/github-actions/cache/#github-cache
[looking for the perfect dockerfile for rust]: https://www.reddit.com/r/rust/comments/16bswvl/comment/jzh6enu/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button
[multi-platform image]: https://docs.docker.com/build/ci/github-actions/multi-platform/
[nested extractor]: https://docs.rs/axum/0.7.5/axum/extract/index.html#accessing-other-extractors-in-fromrequest-or-fromrequestparts-implementations
[rust linker fails when using target-feature=+crt-static on nightly]: https://stackoverflow.com/questions/76604929
[static and dynamic c runtimes]: https://doc.rust-lang.org/reference/linkage.html#static-and-dynamic-c-runtimes
[static linking for rust without glibc - scratch image]: https://users.rust-lang.org/t/static-linking-for-rust-without-glibc-scratch-image/112279/5
[supercharging your rust static executables with mimalloc]: https://www.tweag.io/blog/2023-08-10-rust-static-link-with-mimalloc/
[testing alternative c memory allocators pt 2: the musl mystery]: https://www.linkedin.com/pulse/testing-alternative-c-memory-allocators-pt-2-musl-mystery-gomes/
[use multi-stage docker builds for statically-linked rust binaries]: https://dev.to/deciduously/use-multi-stage-docker-builds-for-statically-linked-rust-binaries-3jgd
[`alpine-mimalloc`]: https://github.com/emerzon/alpine-mimalloc
[`axum` with redis example]: https://github.com/tokio-rs/axum/blob/main/examples/tokio-redis/src/main.rs
[`cargo-chef`]: https://github.com/LukeMathWalker/cargo-chef
[`chainguard/static`]: https://hub.docker.com/r/chainguard/static
[`kube.rs` best practices]: https://kube.rs/controllers/security/#base-images
[`mimalloc`]: https://github.com/marvin-hansen/mimalloc
[`mimalloc` commentary]: https://github.com/clux/muslrust/issues/142
[`mimalloc` crate]: https://docs.rs/mimalloc/latest/mimalloc/
[`muslrust`]: https://github.com/clux/muslrust
[`rust-alpine-mimalloc`]: https://github.com/tweag/rust-alpine-mimalloc
[`rust-musl-builder`]: https://github.com/emk/rust-musl-builder
[`rust-static-builder`]: https://github.com/fornwall/rust-static-builder
[`target-feature`]: https://doc.rust-lang.org/rustc/codegen-options/index.html#target-feature
