# Offline source overlay on the independently verified locked dependency image.
# This is a staging artifact; it does not replace the normal locked Docker build.
ARG BASE_IMAGE=madar-backend:b0fdfe049510724c06a04706390cd174ea57a1d1
FROM ${BASE_IMAGE}
USER root
RUN rm -rf /app
COPY web/backend /app
RUN chmod -R a+rX /app && python /app/scripts/verify_installed_constraints.py && python -m pip check
ARG SOURCE_SHA
LABEL com.madar.staging.owner="architecture-hardening-20261016" \
      org.opencontainers.image.revision="${SOURCE_SHA}"
ENV MADAR_RELEASE_SHA=${SOURCE_SHA}
WORKDIR /app
USER 65534:65534
