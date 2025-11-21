FROM python:3.11

WORKDIR /app

COPY reqs.txt .

RUN pip install -r reqs.txt

COPY . .

EXPOSE 5600

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "Orders.py"]
