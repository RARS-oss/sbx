# Build sbx, then ship it in a slim image with the toolchains it sandboxes.
# sbx builds its own isolation (user namespaces + seccomp + pivot_root) at runtime, so the container
# needs unprivileged user namespaces allowed. On Docker that usually means:
#     docker run --security-opt seccomp=unconfined ghcr.io/rars-oss/sbx run -- <cmd>
# (Docker's default seccomp profile blocks the clone/unshare namespace flags sbx uses; unconfined —
# or a profile that allows them — lets sbx build its sandbox. sbx then applies its own seccomp inside.)
FROM rust:1-slim AS build
WORKDIR /src
COPY . .
RUN cargo build --release -p sbx-cli && strip target/release/sbx

FROM debian:stable-slim
# Toolchains for the code sbx sandboxes (AddressSanitizer needs the compilers). Extend as needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/sbx /usr/local/bin/sbx
RUN useradd -m runner
USER runner
WORKDIR /work
ENTRYPOINT ["sbx"]
CMD ["selftest"]
