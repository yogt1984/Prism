# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY src/ src/

# Install the package and all runtime dependencies
RUN pip install --no-cache-dir --prefix=/install . && \
    pip install --no-cache-dir --prefix=/install "scikit-learn>=1.4.0" || true

# Stage 2: Runtime
FROM python:3.12-slim

# Create non-root user
RUN groupadd -g 1000 prism && \
    useradd -u 1000 -g prism -m -s /bin/bash prism

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source and install package (deps already present)
WORKDIR /app
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY pyproject.toml .
RUN pip install --no-cache-dir --no-deps -e .

# Create data directory for SQLite with correct ownership
RUN mkdir -p /app/data && chown -R prism:prism /app/data
VOLUME ["/app/data"]

# Switch to non-root user
USER prism

EXPOSE 8000

# Default: run the scheduler
CMD ["prism", "run"]
