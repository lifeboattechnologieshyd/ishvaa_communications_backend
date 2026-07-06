FROM python:3.13-slim-bookworm AS base

FROM base AS python-build-stage

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    python3-dev

COPY requirements.txt ./
COPY requirements ./requirements

RUN pip wheel --wheel-dir /usr/src/app/wheels -r requirements.txt


FROM base AS alloy-download-stage

ARG ALLOY_VERSION=1.11.0
ARG TARGETARCH
ARG BUILDPLATFORM

WORKDIR /tmp

RUN echo "Running on ${BUILDPLATFORM} for ${TARGETARCH}"

RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    unzip \
    ca-certificates \
    && curl -LO "https://github.com/grafana/alloy/releases/download/v${ALLOY_VERSION}/alloy-linux-${TARGETARCH}.zip" \
    && unzip "alloy-linux-${TARGETARCH}.zip" \
    && chmod +x "alloy-linux-${TARGETARCH}" \
    && mv "alloy-linux-${TARGETARCH}" alloy


FROM base AS final

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /project/

RUN apt-get update && apt-get install --no-install-recommends -y \
    libpq5 \
    procps \
    && apt-get purge -y --auto-remove \
    -o APT::AutoRemove::RecommendsImportant=false \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-build-stage /usr/src/app/wheels /wheels/

RUN pip install --no-cache-dir \
    --no-index \
    --find-links=/wheels/ \
    /wheels/* \
    && rm -rf /wheels/

COPY --from=alloy-download-stage /tmp/alloy /usr/local/bin/alloy

RUN chmod +x /usr/local/bin/alloy

COPY deploy/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY deploy/docker/prestop.sh /usr/local/bin/prestop.sh

RUN chmod +x \
    /usr/local/bin/entrypoint.sh \
    /usr/local/bin/prestop.sh

COPY . /project/

RUN chmod +x /project/scripts/* 2>/dev/null || true

EXPOSE 8000 12345

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]