FROM node:22-bookworm

ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    openssh-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Miniforge
ENV CONDA_DIR=/opt/conda
ENV PATH="${CONDA_DIR}/bin:${PATH}"

RUN case "${TARGETARCH}" in \
      "amd64") ARCH="x86_64" ;; \
      "arm64") ARCH="aarch64" ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && curl -fsSL \
      "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${ARCH}.sh" \
      -o /tmp/miniforge.sh \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh

# Python environment
RUN mamba create -y -n agent python=3.12 pip

ENV PATH="/opt/conda/envs/agent/bin:/opt/conda/bin:${PATH}"

# Codex + Claude
RUN npm install -g \
    @openai/codex \
    @anthropic-ai/claude-code

# Non-root user
RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace

USER agent

# Clone your repo
RUN git clone \
    https://github.com/dexterpratt/symposium_agentathon.git \
    /workspace/symposium_agentathon

COPY --chown=agent:agent run-agent /usr/local/bin/run-agent
RUN chmod +x /usr/local/bin/run-agent

WORKDIR /workspace/symposium_agentathon

ENTRYPOINT ["/usr/local/bin/run-agent"]
