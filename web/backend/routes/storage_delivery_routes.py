from fastapi import APIRouter, Request
from services.storage_delivery_service import stream_storage_object

router = APIRouter(tags=['Public avatars'])


@router.api_route('/assets/avatars/{path:path}', methods=['GET', 'HEAD'])
def public_avatar(path: str, request: Request):
    return stream_storage_object(bucket='avatars', path=path, request=request, public_avatar=True, headers={
        'Cache-Control': 'public, max-age=3600', 'CDN-Cache-Control': 'public, max-age=3600',
        'Content-Encoding': 'identity', 'X-Content-Type-Options': 'nosniff',
    })
