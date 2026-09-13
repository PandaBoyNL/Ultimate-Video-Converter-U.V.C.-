FROM alpine:latest
RUN apk add --no-cache python3 py3-pip ffmpeg bash
RUN pip3 install --no-cache-dir flask --break-system-packages
COPY app.py /app.py
CMD ["python3", "-u", "/app.py"]