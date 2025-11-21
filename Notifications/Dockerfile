FROM python:3.11

WORKDIR /app

COPY reqs.txt .

RUN pip install -r reqs.txt

COPY . .

EXPOSE 5800

CMD ["python", "Notifications.py"]
