FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    OPSPULSE_SECRET_KEY=change-me \
    ADMIN_USER=admin \
    ADMIN_PASS=admin123
EXPOSE 5000
CMD ["python", "app.py"]
