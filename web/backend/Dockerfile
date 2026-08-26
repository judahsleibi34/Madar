FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

WORKDIR /app

COPY requirements.txt constraints.txt ./

RUN python -m pip install --no-cache-dir pip==26.2.1 \
    && pip install --no-cache-dir -r requirements.txt -c constraints.txt \
    && python -m pip check

# Release metadata changes for every immutable build. Declare it only after
# the expensive dependency layer so a new SHA cannot invalidate locked deps.
ARG MADAR_RELEASE_SHA=development
ARG MADAR_BUILD_TIMESTAMP=unknown

COPY . .

# Keep repo-root style script paths working in the backend container. Release
# worktrees are created under systemd UMask=0077, so normalize only immutable
# image-layer application files for the non-root runtime user.
RUN mkdir -p /test-repository/backend /test-repository/frontend \
    && chmod -R a+rX /app \
    && python scripts/verify_installed_constraints.py \
    && ln -s . backend

LABEL org.opencontainers.image.revision=$MADAR_RELEASE_SHA \
      org.opencontainers.image.created=$MADAR_BUILD_TIMESTAMP
ENV MADAR_RELEASE_SHA=$MADAR_RELEASE_SHA \
    MADAR_BUILD_TIMESTAMP=$MADAR_BUILD_TIMESTAMP

USER 65534:65534

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
