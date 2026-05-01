FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    tor \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Match the app container's shared group so it can read the control cookie
# without opening the control port more broadly.
RUN groupadd --gid 2000 tor-cookie \
    && usermod --gid tor-cookie debian-tor \
    && mkdir -p /var/lib/tor \
    && chown -R debian-tor:tor-cookie /var/lib/tor \
    && chmod 2750 /var/lib/tor

USER debian-tor

CMD ["tor", "-f", "/etc/tor/torrc"]
