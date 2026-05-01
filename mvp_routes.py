"""
MVP console and service manifest routes.

Provides a single operator-facing entry point that ties together the hardened
chat, HTTP mail, and burner workflows exposed by the application.
"""

from flask import jsonify, render_template


def register_mvp_routes(app):
    """Register the operator console and a JSON service manifest."""

    def _hostname():
        return app.config.get("hostname", "localhost")

    def _build_manifest():
        services = [
            {
                "name": "secure-chat",
                "label": "Secure chat rooms",
                "href": "/chat",
                "api": ["/chat/create", "/chat/room/<room_id>/messages", "/chat/room/<room_id>/key"],
                "constraints": {
                    "storage": "memory-only",
                    "retention_seconds": 180,
                    "max_message_length": 500,
                    "content_type": "plain-text or ENC: encrypted payloads",
                },
            },
            {
                "name": "health",
                "label": "Operational health",
                "href": "/health",
                "api": ["/health", "/version", "/chat/stats"],
                "constraints": {
                    "auth": "none",
                    "purpose": "monitoring and orchestration",
                },
            },
        ]

        if app.config.get("OPSECHAT_ENABLE_HTTP_MAIL"):
            services.append({
                "name": "http-mail",
                "label": "Restricted HTTP mail",
                "href": None,
                "api": [
                    "/<secret-path>/mail/new",
                    "/<secret-path>/mail/<address>/send",
                    "/<secret-path>/mail/<address>/inbox?key=<read_key>",
                ],
                "constraints": {
                    "storage": "memory-only",
                    "retention_hours": 24,
                    "max_message_length": 2000,
                    "exposure": "restricted; secret path intentionally omitted",
                },
            })

        if app.config.get("OPSECHAT_ENABLE_EMAIL_STACK"):
            services.append({
                "name": "burner-receive",
                "label": "Restricted burner inboxes",
                "href": None,
                "api": [
                    "/<secret-path>/email/burner",
                    "/<secret-path>/email/burner/list.json",
                ],
                "constraints": {
                    "storage": "memory-only",
                    "retention_hours": 24,
                    "delivery_model": "receive-only aliases backed by HTTP mailboxes",
                    "exposure": "restricted; secret path intentionally omitted",
                },
            })

        return {
            "console": "/console",
            "hostname": _hostname(),
            "profile": "extended" if app.config.get("OPSECHAT_ENABLE_EXTENDED_SERVICES") else "core",
            "extended_services_enabled": bool(app.config.get("OPSECHAT_ENABLE_EXTENDED_SERVICES")),
            "legacy_chat_enabled": bool(app.config.get("OPSECHAT_ENABLE_LEGACY_CHAT")),
            "services": services,
        }

    @app.route("/console", methods=["GET"])
    def mvp_console():
        manifest = _build_manifest()
        return render_template("mvp_console.html", manifest=manifest)

    @app.route("/", methods=["GET"])
    def console_root():
        manifest = _build_manifest()
        return render_template("mvp_console.html", manifest=manifest)

    @app.route("/console/api", methods=["GET"])
    def mvp_console_api():
        return jsonify(_build_manifest())

    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        manifest = _build_manifest()
        return render_template("dashboard.html", manifest=manifest)
