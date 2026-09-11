FROM python:3.12-slim

WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install edgeport
RUN pip install --no-cache-dir .

EXPOSE 8000 4040

ENTRYPOINT ["edgeport"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
