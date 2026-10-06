"""Narrow email-link callback; it is not a public Supabase reverse proxy."""
import os
from urllib.parse import urlsplit, parse_qs
import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

router = APIRouter(tags=['Email callbacks'])


def allowed_frontend_redirect(value: str) -> bool:
    base = os.getenv('FRONTEND_PRIMARY_URL') or os.getenv('FRONTEND_URL') or ''
    expected, actual = urlsplit(base), urlsplit(value)
    if (expected.scheme != 'https' or actual.scheme != expected.scheme or actual.netloc != expected.netloc
            or actual.username or actual.password or actual.path not in {'', '/', '/verify-email', '/reset-password'}):
        return False
    # The recovery flow binds its request nonce in this query parameter.
    query = parse_qs(actual.query, keep_blank_values=True)
    return not query or (actual.path == '/reset-password' and set(query) == {'request_token'} and len(query['request_token']) == 1)


@router.get('/auth/v1/verify')
def verify_email_callback(request: Request):
    params = dict(request.query_params)
    if len(request.query_params.multi_items()) != len(params):
        raise HTTPException(400, 'Invalid verification link', headers={'Cache-Control': 'no-store'})
    if (set(params) - {'token', 'type', 'redirect_to'} or not params.get('token')
            or params.get('type') not in {'signup', 'recovery', 'invite', 'email_change', 'email'}
            or ('redirect_to' in params and not allowed_frontend_redirect(params['redirect_to']))):
        raise HTTPException(400, 'Invalid verification link', headers={'Cache-Control': 'no-store'})
    try:
        # Requests does not log callback URLs at INFO. Never log params/errors:
        # verification tokens and the returned fragment are credentials.
        with requests.Session() as session:
            session.trust_env = False
            result = session.get(os.environ['SUPABASE_URL'].rstrip('/') + '/auth/v1/verify', params=params,
                                 allow_redirects=False, timeout=30)
        location = result.headers.get('Location', '')
        if result.status_code not in {302, 303, 307} or not allowed_frontend_redirect(location):
            raise HTTPException(502, 'Verification unavailable', headers={'Cache-Control': 'no-store'})
        return RedirectResponse(location, status_code=303, headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
    except requests.RequestException:
        raise HTTPException(502, 'Verification unavailable', headers={'Cache-Control': 'no-store'}) from None
