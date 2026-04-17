FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    tor \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/lib/tor \
    && chown -R debian-tor:debian-tor /var/lib/tor \
    && chmod 700 /var/lib/tor

USER debian-tor

CMD ["tor", "-f", "/etc/tor/torrc"]
