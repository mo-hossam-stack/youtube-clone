import time
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from .models import Video


class RateLimitUploadTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='uploaduser', password='pass1234')
        self.client.login(username='uploaduser', password='pass1234')
        self.url = reverse('videos:upload_submit')

    @override_settings(RATE_LIMIT_UPLOAD='3/m', RATE_LIMIT_VOTE='60/m', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_upload_exceeds_limit_returns_429(self):
        for i in range(3):
            resp = self.client.post(self.url)
            self.assertNotEqual(resp.status_code, 429, f"Request {i+1} should not be rate limited yet")

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429)

    @override_settings(RATE_LIMIT_UPLOAD='3/m', RATE_LIMIT_VOTE='60/m', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_upload_retry_after_header(self):
        for _ in range(4):
            self.client.post(self.url)

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429)
        self.assertIn('Retry-After', resp.headers)
        retry_after = int(resp.headers['Retry-After'])
        self.assertGreaterEqual(retry_after, 1)

    @override_settings(RATE_LIMIT_UPLOAD='3/m', RATE_LIMIT_VOTE='60/m', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_upload_limit_does_not_affect_other_users(self):
        for i in range(3):
            resp = self.client.post(self.url)
            self.assertNotEqual(resp.status_code, 429, f"uploaduser request {i+1} should not be rate limited")

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429)

        other_user = User.objects.create_user(username='other', password='pass1234')
        self.client.logout()
        self.client.login(username='other', password='pass1234')

        for i in range(3):
            resp = self.client.post(self.url)
            self.assertNotEqual(resp.status_code, 429, f"Other user request {i+1} should not be affected")

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429)

        self.client.logout()
        self.client.login(username='uploaduser', password='pass1234')
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429, "uploaduser should still be rate limited")

    @override_settings(RATE_LIMIT_UPLOAD='2/3s', RATE_LIMIT_VOTE='60/m', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_upload_limit_resets_after_window(self):
        for _ in range(2):
            self.client.post(self.url)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 429)

        time.sleep(3.5)

        resp = self.client.post(self.url)
        self.assertNotEqual(resp.status_code, 429, "Rate limit should reset after window")


class RateLimitVoteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='voteuser', password='pass1234')
        self.client.login(username='voteuser', password='pass1234')
        self.video = Video.objects.create(
            user=self.user,
            title='Test Video',
            file_id='test_file_id',
            video_url='https://example.com/video.mp4',
        )
        self.url = reverse('videos:vote', args=[self.video.id])

    @override_settings(RATE_LIMIT_VOTE='3/m', RATE_LIMIT_UPLOAD='5/h', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_vote_exceeds_limit_returns_429(self):
        for i in range(3):
            resp = self.client.post(self.url, {'vote': 'like'})
            self.assertNotEqual(resp.status_code, 429, f"Vote {i+1} should not be rate limited yet")

        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertEqual(resp.status_code, 429)

    @override_settings(RATE_LIMIT_VOTE='3/m', RATE_LIMIT_UPLOAD='5/h', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_vote_retry_after_header(self):
        for _ in range(4):
            self.client.post(self.url, {'vote': 'like'})

        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertEqual(resp.status_code, 429)
        self.assertIn('Retry-After', resp.headers)
        self.assertGreaterEqual(int(resp.headers['Retry-After']), 1)

    @override_settings(RATE_LIMIT_VOTE='2/3s', RATE_LIMIT_UPLOAD='5/h', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_vote_limit_resets_after_window(self):
        for _ in range(2):
            self.client.post(self.url, {'vote': 'like'})
        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertEqual(resp.status_code, 429)

        time.sleep(3.5)

        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertNotEqual(resp.status_code, 429, "Vote rate limit should reset after window")

    @override_settings(RATE_LIMIT_VOTE='3/m', RATE_LIMIT_UPLOAD='5/h', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_anonymous_vote_is_ip_limited(self):
        self.client.logout()
        for i in range(3):
            resp = self.client.post(self.url, {'vote': 'like'})
            self.assertNotEqual(resp.status_code, 429, f"Anonymous vote {i+1}")

        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertEqual(resp.status_code, 429)

    @override_settings(RATE_LIMIT_VOTE='3/m', RATE_LIMIT_UPLOAD='5/h', RATE_LIMIT_LOGIN='5/m', RATE_LIMIT_REGISTER='5/m')
    def test_logged_in_user_does_not_share_anonymous_limit(self):
        self.client.logout()
        for _ in range(3):
            self.client.post(self.url, {'vote': 'like'})
        resp = self.client.post(self.url, {'vote': 'like'})
        self.assertEqual(resp.status_code, 429)

        self.client.login(username='voteuser', password='pass1234')
        for i in range(3):
            resp = self.client.post(self.url, {'vote': 'like'})
            self.assertNotEqual(resp.status_code, 429, f"Authenticated vote {i+1} should have own limit")


