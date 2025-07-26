FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    net-tools \
    inotify-tools \
    quota \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install watchdog python-dotenv

# Copy the application code
COPY . .

# Create shared storage directory
RUN mkdir -p /shared_storage

# Set up disk quota
RUN echo "*/shared_storage 5G" > /etc/fstab.quota \
    && echo "quota /shared_storage ext4 usrquota,grpquota 0 0" >> /etc/fstab

# Create startup script
RUN echo '#!/bin/bash\n\
# Create symlink to user\'s Downloads/Shared folder\nif [ ! -L "/shared_storage" ]; then\n    USER_HOME=$(eval echo ~$USER)\n    mkdir -p "$USER_HOME/Downloads/Shared"\n    mount --bind "$USER_HOME/Downloads/Shared" /shared_storage\n    chmod 777 /shared_storage\nfi\n\n# Start the application\npython main.py\n' > /start.sh \
    && chmod +x /start.sh

# Expose the default port
EXPOSE 5000

# Set the default command to run the server
CMD ["/start.sh"]
CMD ["python", "main.py", "server", "--port", "5000"]
