import re

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest import mock

from .models import Video

VALID = re.compile(r"^[A-Za-z0-9]{8}$")


class PublicIdModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="piduser", password="pass1234")

    def _create(self, **kwargs):
        return Video.objects.create(user=self.user, title="t", **kwargs)

    def test_generated_on_create(self):
        v = self._create()
        self.assertTrue(v.public_id)

    def test_exactly_eight_chars(self):
        v = self._create()
        self.assertEqual(len(v.public_id), 8)

    def test_base62_only(self):
        v = self._create()
        self.assertRegex(v.public_id, VALID)

    def test_two_videos_different_ids(self):
        v1, v2 = self._create(), self._create()
        self.assertNotEqual(v1.public_id, v2.public_id)

    def test_immutable_after_first_assignment(self):
        v = self._create()
        v.public_id = "changed0"
        with self.assertRaises(ValueError):
            v.save()

    def test_ordinary_update_preserves_public_id(self):
        v = self._create()
        original = v.public_id
        v.title = "updated"
        v.save()
        self.assertEqual(v.public_id, original)

    def test_explicit_public_id_respected(self):
        v = self._create(public_id="AbC123xY")
        self.assertEqual(v.public_id, "AbC123xY")

    def test_uniqueness_enforced(self):
        v = self._create()
        with self.assertRaises(IntegrityError):
            self._create(public_id=v.public_id)


class PublicIdUrlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="urluser", password="pass1234")
        self.other = User.objects.create_user(username="other", password="pass1234")
        self.video = Video.objects.create(
            user=self.user,
            title="t",
            status="safe",
            file_id="fid",
            video_url="https://example.com/v.mp4",
        )

    def test_detail_resolves_by_public_id(self):
        resp = self.client.get(f"/{self.video.public_id}")
        self.assertContains(resp, self.video.title)

    def test_integer_url_is_404(self):
        resp = self.client.get(f"/{self.video.id}")
        self.assertEqual(resp.status_code, 404)

    def test_malformed_invalid_chars_is_404(self):
        resp = self.client.get("/garbage!7")
        self.assertEqual(resp.status_code, 404)

    def test_wrong_length_is_404(self):
        resp = self.client.get("/ABCDEFGH")
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_valid_id_is_404(self):
        resp = self.client.get("/ZZZZZZZZ")
        self.assertEqual(resp.status_code, 404)

    def test_list_links_use_public_id(self):
        resp = self.client.get(reverse("videos:list"))
        self.assertContains(resp, f"href=\"/{self.video.public_id}\"")

    def test_channel_links_use_public_id(self):
        resp = self.client.get(reverse("videos:channel", args=[self.user.username]))
        self.assertContains(resp, f"href=\"/{self.video.public_id}\"")


class PublicIdAuthorizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="pass1234")
        self.other = User.objects.create_user(username="intruder", password="pass1234")
        self.video = Video.objects.create(
            user=self.user, title="t", status="pending"
        )

    def test_owner_can_delete(self):
        self.client.login(username="owner", password="pass1234")
        resp = self.client.post(f"/{self.video.public_id}/delete/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Video.objects.filter(pk=self.video.pk).exists())

    def test_non_owner_cannot_delete(self):
        self.client.login(username="intruder", password="pass1234")
        resp = self.client.post(f"/{self.video.public_id}/delete/")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Video.objects.filter(pk=self.video.pk).exists())

    def test_owner_can_access_upload_status(self):
        self.client.login(username="owner", password="pass1234")
        resp = self.client.post(reverse("videos:upload_status", args=[self.video.public_id]))
        self.assertEqual(resp.status_code, 200)

    def test_non_owner_cannot_access_upload_status(self):
        self.client.login(username="intruder", password="pass1234")
        resp = self.client.post(reverse("videos:upload_status", args=[self.video.public_id]))
        self.assertEqual(resp.status_code, 404)

    def test_vote_allows_any_authenticated_user(self):
        self.client.login(username="intruder", password="pass1234")
        resp = self.client.post(f"/{self.video.public_id}/vote/", {"vote": "like"})
        self.assertEqual(resp.status_code, 200)

    def test_upload_status_does_not_leak_integer_id(self):
        self.client.login(username="owner", password="pass1234")
        resp = self.client.post(reverse("videos:upload_status", args=[self.video.public_id]))
        self.assertNotIn("video_id", resp.json())

    def test_vote_uses_public_id_not_integer(self):
        self.client.login(username="intruder", password="pass1234")
        resp = self.client.post(f"/{self.video.id}/vote/", {"vote": "like"})
        self.assertEqual(resp.status_code, 404)
        resp = self.client.post(f"/{self.video.public_id}/vote/", {"vote": "like"})
        self.assertEqual(resp.status_code, 200)


class PublicIdMiddlewareTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="mw", password="pass1234")
        self.client.login(username="mw", password="pass1234")
        self.video = Video.objects.create(
            user=self.user, title="t", status="safe",
            file_id="f", video_url="https://example.com/v.mp4",
        )

    @override_settings(RATE_LIMIT_VOTE="3/m", RATE_LIMIT_UPLOAD="5/h")
    def test_valid_public_id_vote_is_rate_limited(self):
        url = f"/{self.video.public_id}/vote/"
        for _ in range(3):
            self.assertEqual(self.client.post(url, {"vote": "like"}).status_code, 200)
        self.assertEqual(self.client.post(url, {"vote": "like"}).status_code, 429)

    @override_settings(RATE_LIMIT_VOTE="3/m", RATE_LIMIT_UPLOAD="5/h")
    def test_non_public_id_vote_not_rate_limited(self):
        # not 8 alphanumeric chars -> middleware regex doesn't match -> reaches view -> 404
        url = "/short/vote/"
        for _ in range(5):
            self.assertEqual(self.client.post(url, {"vote": "like"}).status_code, 404)

    @override_settings(RATE_LIMIT_VIEW_DETAIL="1/m")
    def test_valid_public_id_detail_is_rate_limited_by_get_limit(self):
        url = f"/{self.video.public_id}"
        self.assertNotEqual(self.client.get(url).status_code, 429)
        self.assertEqual(self.client.get(url).status_code, 429)  # 1/m exceeded

    @override_settings(RATE_LIMIT_VIEW_DETAIL="1/m")
    def test_wrong_length_detail_not_rate_limited(self):
        resp = self.client.get("/abcd")
        self.assertEqual(resp.status_code, 404)
