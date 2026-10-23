import pytest
from pydantic import ValidationError
from app.core.config import Settings


def make_settings(**overrides):
    return Settings(
        _env_file=None,
        DATABASE_URL='postgresql://unused/test',
        JWT_SECRET_KEY='fixture-only-key-not-used-by-any-deployment-123',
        **overrides,
    )


def test_cookie_defaults_to_same_origin_lax_policy():
    assert make_settings().SESSION_COOKIE_SAMESITE == 'lax'


def test_cross_site_desktop_cookie_requires_secure_transport():
    with pytest.raises(ValidationError, match='SameSite=None session cookies require COOKIE_SECURE=true'):
        make_settings(SESSION_COOKIE_SAMESITE='none', COOKIE_SECURE=False)
    assert make_settings(SESSION_COOKIE_SAMESITE='none', COOKIE_SECURE=True).SESSION_COOKIE_SAMESITE == 'none'
