FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    net-tools \
    inotify-tools \
    quota \
    rsync \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create shared storage directory
RUN mkdir -p /shared_storage

# Create a non-root user and give permissions
RUN useradd -m appuser && \
    chown -R appuser:appuser /app /shared_storage && \
    chmod 777 /shared_storage

# Switch to non-root user
USER appuser

# Create startup script
RUN echo '#!/bin/bash\n\
# Create the shared directory if it does not exist\nSHARED_DIR="$HOME/Downloads/DiskStorage"\nif [ ! -d "$SHARED_DIR" ]; then\n    mkdir -p "$SHARED_DIR"\n    chmod 777 "$SHARED_DIR"\n    echo "Created shared directory: $SHARED_DIR"\nelse\n    echo "Using existing shared directory: $SHARED_DIR"\nfi\n\n# Start the application\npython main.py\n' > /app/start.sh \
    && chmod +x /app/start.sh

# Expose the default port
EXPOSE 5000

# Set the default command to run the server
CMD ["/app/start.sh"]
