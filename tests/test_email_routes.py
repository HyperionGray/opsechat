from unittest.mock import patch

from app_factory import create_app


def _init_session(client, user_id="route-test-user"):
    with client.session_transaction() as sess:
        sess["_id"] = user_id
        sess["color"] = (1, 2, 3)


def _build_app():
    app = create_app()
    app.config.update(
        TESTING=True,
        path="testpath",
        hostname="localhost",
        SECRET_KEY="test-secret",
    )
    return app


def test_configure_smtp_and_send_compose_email():
    app = _build_app()

    with app.test_client() as client:
        _init_session(client)

        with patch("email_routes.SMTPTransport.test_connection", return_value=True):
            response = client.post(
                "/testpath/email/config",
                data={
                    "action": "configure_smtp",
                    "smtp_server": "smtp.test.com",
                    "smtp_port": "587",
                    "smtp_username": "user@test.com",
                    "smtp_password": "secret",
                    "use_tls": "true",
                    "smtp_retries": "2",
                    "smtp_backoff_seconds": "0",
                },
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"SMTP configuration saved and verified." in response.data

        with patch("email_routes.SMTPTransport.send_email", return_value=True):
            response = client.post(
                "/testpath/email/compose",
                data={
                    "raw_mode": "false",
                    "from": "sender@example.com",
                    "to": "recipient@example.com",
                    "subject": "SMTP Test",
                    "body": "Message body",
                    "send_via_smtp": "true",
                },
                follow_redirects=True,
            )
        assert response.status_code == 200
        assert b"Email sent successfully via SMTP." in response.data


def test_burner_and_security_routes_work():
    app = _build_app()

    with app.test_client() as client:
        _init_session(client)

        burner_response = client.post(
            "/testpath/email/burner",
            data={"action": "generate"},
            follow_redirects=True,
        )
        assert burner_response.status_code == 200
        assert b"Burner generated successfully" in burner_response.data

        burner_list_response = client.get("/testpath/email/burner/list")
        assert burner_list_response.status_code == 200
        payload = burner_list_response.get_json()
        assert isinstance(payload["burners"], list)
        assert len(payload["burners"]) >= 1

        spoof_response = client.post(
            "/testpath/email/security/spoof-test",
            data={
                "test_type": "detect",
                "test_email": "suspicious@example.com",
                "legitimate_domain": "example.com",
            },
            follow_redirects=True,
        )
        assert spoof_response.status_code == 200
        assert b"Detection Results" in spoof_response.data

        phishing_response = client.post(
            "/testpath/email/security/phishing-sim",
            data={"action": "generate", "template": "generic"},
            follow_redirects=True,
        )
        assert phishing_response.status_code == 200
        assert b"Generated phishing simulation email" in phishing_response.data
