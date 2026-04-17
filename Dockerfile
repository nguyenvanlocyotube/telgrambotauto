FROM python:3.11-slim

WORKDIR /app

# ❗ copy toàn bộ trước (phá cache)
COPY . .

# ❗ ép rebuild
RUN echo "force rebuild v1000"

# install lại từ đầu
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]