FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --system --uid 10001 sentinel && chown -R sentinel /srv
USER sentinel
EXPOSE 8000
# Stateless: all config via environment. --proxy-headers so client IPs in the
# audit trail come from the load balancer's X-Forwarded-For.
# Run migrations as a separate release step:  alembic upgrade head
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
