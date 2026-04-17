"""
MVP console and service manifest routes.

Provides a single operator-facing entry point that ties together the hardened
chat, HTTP mail, and burner workflows exposed by the application.
"""

from flask import jsonify, render_template


def register_mvp_routes(app):
    """Register the operator console and a JSON service manifest."""

    def _secret_path():
        return app.config.get("path", "")

    def _hostname():
        return app.config.get("hostname", "localhost")

    def _build_manifest():
        secret_path = _secret_path()
        secret_prefix = f"/{secret_path}" if secret_path else None

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
                "name": "http-mail",
                "label": "HTTP mail inboxes",
                "href": f"{secret_prefix}/mail" if secret_prefix else None,
                "api": [
                    f"{secret_prefix}/mail/new" if secret_prefix else None,
                    f"{secret_prefix}/mail/<address>/send" if secret_prefix else None,
                    f"{secret_prefix}/mail/<address>/inbox?key=<read_key>" if secret_prefix else None,
                ],
                "constraints": {
                    "storage": "memory-only",
                    "retention_hours": 24,
                    "max_message_length": 2000,
                    "attachments": "not supported",
                },
            },
            {
                "name": "burner-mail",
                "label": "Burner email rotation",
                "href": f"{secret_prefix}/email/burner" if secret_prefix else None,
                "api": [
                    f"{secret_prefix}/email/burner" if secret_prefix else None,
                    f"{secret_prefix}/email/burner/list.json" if secret_prefix else None,
                ],
                "constraints": {
                    "storage": "memory-only",
                    "retention_hours": 24,
                    "send_limit_per_hour": 10,
                    "attachments": "not supported",
                },
            },
            {
                "name": "health",
                "label": "Operational health",
                "href": "/health",
                "api": ["/health", "/chat/stats"],
                "constraints": {
                    "auth": "none",
                    "purpose": "monitoring and orchestration",
                },
            },
        ]

        # Remove unavailable secret-path links while the app is bootstrapping.
        for service in services:
            service["api"] = [endpoint for endpoint in service["api"] if endpoint]

        return {
            "console": "/console",
            "hostname": _hostname(),
            "secret_path": secret_path or None,
            "full_service_path": app.config.get("full_path"),
            "services": services,
        }

    @app.route("/console", methods=["GET"])
    def mvp_console():
        manifest = _build_manifest()
        return render_template("mvp_console.html", manifest=manifest)

    @app.route("/console/api", methods=["GET"])
    def mvp_console_api():
        return jsonify(_build_manifest())
