FROM python:3.10

WORKDIR /app

# Optional build-time environment (used to set default runtime APP_ENVIRONMENT)
ARG APP_ENVIRONMENT=dev
ENV APP_ENVIRONMENT=${APP_ENVIRONMENT}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
