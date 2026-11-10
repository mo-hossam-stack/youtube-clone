from unittest.mock import patch

from django.test import TestCase, override_settings


class HealthLiveTests(TestCase):
    def test_live_returns_alive_without_dependencies(self):
        with patch("config.views._database_status") as database:
            response = self.client.get("/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")
        database.assert_not_called()


class HealthReadyTests(TestCase):
    def test_ready_when_all_dependencies_are_healthy(self):
        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            with patch("config.views._database_status", return_value=(True, "ok")):
                with patch("config.views._migrations_status", return_value=(True, "ok")):
                    with patch("config.views._redis_status", return_value=(True, "ok")):
                        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_database_failure_is_unhealthy(self):
        with patch("config.views._database_status", return_value=(False, "error: down")):
            with patch("config.views._migrations_status", return_value=(True, "ok")):
                with patch("config.views._redis_status", return_value=(True, "ok")):
                    response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unhealthy")

    def test_pending_migrations_are_unhealthy(self):
        with patch("config.views._database_status", return_value=(True, "ok")):
            with patch("config.views._migrations_status", return_value=(False, "pending: 2")):
                with patch("config.views._redis_status", return_value=(True, "ok")):
                    response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["services"]["migrations"], "pending: 2")

    def test_required_redis_failure_is_unhealthy(self):
        with override_settings(REDIS_URL="redis://localhost:6379/0"):
            with patch("config.views._database_status", return_value=(True, "ok")):
                with patch("config.views._migrations_status", return_value=(True, "ok")):
                    with patch("config.views._redis_status", return_value=(False, "degraded: down")):
                        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "unhealthy")

    def test_optional_redis_failure_is_degraded_but_ready(self):
        with override_settings(REDIS_URL=""):
            with patch("config.views._database_status", return_value=(True, "ok")):
                with patch("config.views._migrations_status", return_value=(True, "ok")):
                    with patch("config.views._redis_status", return_value=(False, "degraded: down")):
                        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "degraded")

    def test_legacy_health_path_matches_readiness(self):
        with patch("config.views._database_status", return_value=(True, "ok")):
            with patch("config.views._migrations_status", return_value=(True, "ok")):
                with patch("config.views._redis_status", return_value=(True, "ok")):
                    response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
