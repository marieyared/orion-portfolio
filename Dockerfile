# Hosts orion_api.py on any Docker-compatible PaaS (Render, Railway, Fly.io, Heroku, etc).
# Build:  docker build -t orion-api .
# Run:    docker run -p 8787:8787 orion-api
# In cloud, the platform injects PORT and the app binds 0.0.0.0 automatically.

FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY orion_api.py .

EXPOSE 8787

CMD ["python", "-u", "orion_api.py"]
