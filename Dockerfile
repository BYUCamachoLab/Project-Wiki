FROM python:3.9-slim

WORKDIR /app

# Copy everything (see .dockerignore for exclusions)
COPY . /app/

# System build dependencies needed for C-extension packages (cffi, bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    python3-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r macosx/requirements.txt

# Create the log directory (same basedir pattern as uploads — /Project_Wiki_Data/log/).
# In production this path is bind-mounted from the host via docker-compose.
RUN mkdir -p /Project_Wiki_Data/log

EXPOSE 8080

# Shell-form CMD so the Python one-liner doesn't need JSON-array escaping.
# Uses 'from app import create_app' directly (not manage.py) to avoid
# importing flask_script at serve time.
# host= and port= used separately because waitress==1.0.2 has no listen= kwarg.
CMD python -c "from app import create_app; from waitress import serve; app = create_app(); serve(app, host='0.0.0.0', port=8080, threads=4)"
