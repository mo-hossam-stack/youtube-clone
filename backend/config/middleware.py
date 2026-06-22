import re
import time
from django.conf import settings
from django.http import JsonResponse
from django_ratelimit.core import is_ratelimited

_PERIODS = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
_rate_re = re.compile(r'([\d]+)/([\d]*)([smhd])?')


def _parse_rate(rate):
    count, multi, period = _rate_re.match(rate).groups()
    count = int(count)
    if not period:
        period = 's'
    seconds = _PERIODS[period.lower()]
    if multi:
        seconds = seconds * int(multi)
    return count, seconds


def _get_window_seconds(rate):
    return _parse_rate(rate)[1]


class ThrottleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST':
            return self.get_response(request)

        response = self._apply_rate_limits(request)
        if response is not None:
            return response

        return self.get_response(request)

    def _apply_rate_limits(self, request):
        path = request.path_info

        if re.match(r'^/accounts/login/', path):
            return self._check_limit(request, 'ip', settings.RATE_LIMIT_LOGIN, 'login')

        if re.match(r'^/accounts/register/', path):
            return self._check_limit(request, 'ip', settings.RATE_LIMIT_REGISTER, 'register')

        if re.match(r'^/upload/submit/', path):
            return self._check_limit(request, 'user_or_ip', settings.RATE_LIMIT_UPLOAD, 'upload')

        if re.match(r'^/\d+/vote/', path):
            return self._check_limit(request, 'user_or_ip', settings.RATE_LIMIT_VOTE, 'vote')

        return None

    def _check_limit(self, request, key, rate, group):
        limited = is_ratelimited(
            request,
            group=group,
            key=key,
            rate=rate,
            method=('POST',),
            increment=True,
        )
        if limited:
            return self._rate_limited_response(rate)
        return None

    def _rate_limited_response(self, rate):
        window = _get_window_seconds(rate)
        return JsonResponse(
            {'error': 'Rate limit exceeded', 'retry_after': window},
            status=429,
            headers={'Retry-After': str(window)},
        )
