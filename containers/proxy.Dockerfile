FROM caddy:2-alpine

# The upstream image grants caddy a file capability for binding low ports.
# We only bind 8087, and no-new-privileges blocks exec of binaries with file
# capabilities, so drop it to keep the container hardened and startable.
RUN apk add --no-cache libcap \
    && setcap -r /usr/bin/caddy \
    && apk del libcap

COPY containers/Caddyfile /etc/caddy/Caddyfile
