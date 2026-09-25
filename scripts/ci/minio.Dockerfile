# Disposable CI storage only; not a supported production distribution.
FROM golang:1.25.14-alpine3.24@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59 AS build
WORKDIR /src
ADD --checksum=sha256:45521908307306e925c98d629e1c17d78c8b72b6ee242b1bfb1409f7d8ee5841 https://codeload.github.com/minio/minio/tar.gz/9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a /tmp/minio.tar.gz
RUN tar -xzf /tmp/minio.tar.gz --strip-components=1 \
    && CGO_ENABLED=0 GOTOOLCHAIN=local go build -mod=readonly -trimpath -o /out/minio . \
    && cp LICENSE /out/LICENSE

FROM alpine:3.22.6@sha256:5291449c3df73caf6ed85e649dec1b9e818b39a5d8c871e97afc13e9cd5e8fa8
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /out/LICENSE /usr/share/licenses/minio/LICENSE
RUN mkdir /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 9000
ENTRYPOINT ["minio"]
CMD ["server", "/data"]
