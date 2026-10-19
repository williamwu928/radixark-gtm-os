FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh","-c","streamlit run src/gtm_os/app.py --server.port=${PORT:-8080} --server.address=0.0.0.0"]
