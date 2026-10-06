"""Serve Storage bytes through the API without disclosing provider URLs or keys."""
import os
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask


def validate_object_path(path: str) -> str:
    if not path or any(part in {'', '.', '..'} for part in path.split('/')) or any(c in path for c in ('\\', '\x00', '\r', '\n')):
        raise HTTPException(404, 'Asset not found', headers={'Cache-Control': 'no-store'})
    return path


def stream_storage_object(*, bucket: str, path: str, request: Request, headers: dict, public_avatar: bool = False):
    # There is deliberately no public bucket parameter in the avatar route.
    if bucket not in {'avatars', 'builder-assets'} or (public_avatar and bucket != 'avatars'):
        raise HTTPException(404, 'Asset not found')
    path = validate_object_path(path)
    base = os.environ['SUPABASE_URL'].rstrip('/')
    key = os.environ['SUPABASE_SERVICE_KEY']
    client = httpx.Client(timeout=httpx.Timeout(30, read=60), follow_redirects=False, trust_env=False)
    upstream = None
    def close():
        if upstream is not None:
            upstream.close()
        client.close()
    forwarded = {'apikey': key, 'Authorization': f'Bearer {key}', 'Accept-Encoding': 'identity'}
    for name in ('Range', 'If-Range', 'If-None-Match', 'If-Modified-Since'):
        if name in request.headers:
            forwarded[name] = request.headers[name]
    mode = 'public/' if public_avatar else ''
    url = f'{base}/storage/v1/object/{mode}{bucket}/{quote(path, safe="/")}'
    try:
        upstream = client.send(client.build_request(request.method, url, headers=forwarded), stream=True)
        if upstream.status_code not in {200, 206, 304, 416}:
            status = 404 if upstream.status_code in {400, 403, 404} else 502
            close()
            raise HTTPException(status, 'Asset unavailable', headers={'Cache-Control': 'no-store', 'CDN-Cache-Control': 'no-store'})
        response_headers = dict(headers)
        for name in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'ETag', 'Last-Modified'):
            if name in upstream.headers:
                response_headers[name] = upstream.headers[name]
        if upstream.headers.get('content-encoding', 'identity') != 'identity':
            raise ValueError('unexpected_storage_encoding')
        if public_avatar and upstream.status_code in {200, 206} and upstream.headers.get('content-type', '').split(';')[0] not in {'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif'}:
            close()
            raise HTTPException(404, 'Asset not found', headers={'Cache-Control': 'no-store'})
        if upstream.status_code == 416:
            # Storage error JSON can contain provider details; relay only range semantics.
            response_headers.pop('Content-Length', None)
            close()
            return Response(status_code=416, headers=response_headers)
        if request.method == 'HEAD' or upstream.status_code == 304:
            status = upstream.status_code
            close()
            return Response(status_code=status, headers=response_headers)
        def chunks():
            try:
                yield from upstream.iter_raw()
            finally:
                close()
        return StreamingResponse(chunks(), status_code=upstream.status_code, headers=response_headers, background=BackgroundTask(close))
    except (httpx.HTTPError, ValueError) as error:
        close()
        raise HTTPException(502, 'Asset unavailable', headers={'Cache-Control': 'no-store', 'CDN-Cache-Control': 'no-store'}) from error
