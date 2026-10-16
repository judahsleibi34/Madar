# Offline source overlay on the independently verified locked dependency image.
# This is a staging artifact; it does not replace the normal locked Docker build.
ARG BASE_IMAGE=madar-backend:b0fdfe049510724c06a04706390cd174ea57a1d1
FROM ${BASE_IMAGE}
USER root
RUN rm -rf /app
COPY web/backend /app
RUN chmod -R a+rX /app && python /app/scripts/verify_installed_constraints.py && python -m pip check
ARG SOURCE_SHA
ARG BUILD_TIMESTAMP
LABEL com.madar.staging.owner="architecture-hardening-20261016" \
      com.madar.staging.build_mode="offline-source-overlay" \
      com.madar.staging.base_revision="b0fdfe049510724c06a04706390cd174ea57a1d1" \
      com.madar.release.sha="${SOURCE_SHA}" \
      com.madar.release.built_at="${BUILD_TIMESTAMP}" \
      org.opencontainers.image.revision="${SOURCE_SHA}" \
      org.opencontainers.image.created="${BUILD_TIMESTAMP}"
ENV MADAR_RELEASE_SHA=${SOURCE_SHA}
WORKDIR /app
USER 65534:65534
