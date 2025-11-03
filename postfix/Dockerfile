FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    postfix \
    python3 \
    python3-venv \
    rsyslog \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --no-cache-dir redis httpx dnspython

WORKDIR /app

COPY postfix/main.cf.template /etc/postfix/main.cf.template
COPY postfix/master.cf /etc/postfix/master.cf
COPY postfix/redis-recipient.cf /etc/postfix/redis-recipient.cf
COPY postfix/entrypoint.sh /entrypoint.sh
COPY parser/ /app/parser/

RUN chmod +x /entrypoint.sh

EXPOSE 25

CMD ["/entrypoint.sh"]
