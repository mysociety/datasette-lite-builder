FROM python:3.9-bullseye

ENV DEBIAN_FRONTEND noninteractive
COPY pyproject.toml poetry.loc[k] /
RUN curl -sSL https://install.python-poetry.org | python - && \
    echo "export PATH=\"/root/.local/bin:$PATH\"" > ~/.bashrc && \
    export PATH="/root/.local/bin:$PATH"  && \
    poetry config virtualenvs.create false && \
    poetry self add poetry-bumpversion && \
    poetry install && \
    echo "/workspaces/datasette-lite-builder/src/" > /usr/local/lib/python3.9/site-packages/datasette_lite_builder.pth