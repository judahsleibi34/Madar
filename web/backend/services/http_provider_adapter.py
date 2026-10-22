"""Provider-independent HTTP adapter for allow-listed API providers (C2).

Implements ``ApiProviderAdapter`` for any ``ProviderSpec`` in the operator registry.
Each page is one GET through ``ProviderHttpSession``. Records are mapped
declaratively (id, data, authoritative order, explicit delete flag, event id);
nothing provider- or commerce-specific is hard-coded. The synchronization cursor is
taken only from the final page of a complete pagination; an incomplete pagination
raises before any cursor is produced.
"""

from __future__ import annotations

from services.data_source_api_provider import (
    ProviderErrorCategory,
    ProviderFetchError,
    ProviderFetchRequest,
    ProviderPage,
    ProviderRecord,
)
from services.provider_http_transport import ProviderHttpSession, TransportError
from services.data_source_credential_service import DataSourceCredentialError
from services.provider_credentials import CredentialError
from services.provider_registry import ProviderSpec, ResourceSpec

_CATEGORY_BY_TRANSPORT = {
    "cancelled": ProviderErrorCategory.CANCELLED,
    "timeout": ProviderErrorCategory.TIMEOUT,
    "provider_unreachable": ProviderErrorCategory.UNAVAILABLE,
    "provider_unavailable": ProviderErrorCategory.UNAVAILABLE,
    "request_rejected": ProviderErrorCategory.UNAVAILABLE,
    "redirect_refused": ProviderErrorCategory.UNAVAILABLE,
    "tls_invalid": ProviderErrorCategory.UNAVAILABLE,
    "payload_invalid": ProviderErrorCategory.INVALID_RESPONSE,
    "payload_too_large": ProviderErrorCategory.PAYLOAD_TOO_LARGE,
    "unauthorized": ProviderErrorCategory.UNAUTHORIZED,
    "rate_limited": ProviderErrorCategory.RATE_LIMITED,
    "destination_forbidden": ProviderErrorCategory.DESTINATION_FORBIDDEN,
    "destination_invalid": ProviderErrorCategory.DESTINATION_FORBIDDEN,
    "request_invalid": ProviderErrorCategory.INVALID_RESPONSE,
}


def provider_error(error: TransportError) -> ProviderFetchError:
    return ProviderFetchError(_CATEGORY_BY_TRANSPORT.get(error.code,
                                                         ProviderErrorCategory.UNAVAILABLE))


def _invalid():
    return ProviderFetchError(ProviderErrorCategory.INVALID_RESPONSE)


class HttpApiProviderAdapter:
    def __init__(self, spec: ProviderSpec, session: ProviderHttpSession):
        self.spec = spec
        self.session = session
        self.provider_key = spec.key
        self.supported_resources = frozenset(spec.resources)
        self._final_cursor: str | None = None
        self._completed = False

    def fetch_page(self, request: ProviderFetchRequest) -> ProviderPage:
        resource: ResourceSpec = self.spec.resources[request.resource_type]
        params: dict[str, str] = {}
        if request.sync_cursor:
            params[resource.cursor_param] = request.sync_cursor
        if request.continuation:
            params[resource.page_param] = request.continuation
        if resource.limit_param:
            params[resource.limit_param] = str(max(1, min(resource.page_size,
                                                          request.remaining_records)))
        self.session.cancelled = request.cancelled
        try:
            body = self.session.get_json(resource.path, params, deadline=request.deadline)
        except TransportError as error:
            raise provider_error(error) from None
        if not isinstance(body, dict) or not isinstance(body.get(resource.records_field), list):
            raise _invalid()
        records = [self._record(resource, item) for item in body[resource.records_field]]
        continuation = body.get(resource.next_page_field)
        if continuation is not None and not isinstance(continuation, str):
            raise _invalid()
        if continuation and body.get(resource.next_cursor_field) is not None:
            raise _invalid()  # a commit cursor belongs only to a complete traversal
        if continuation is None:
            cursor = body.get(resource.next_cursor_field)
            if not isinstance(cursor, str) or not 0 < len(cursor) <= 1024:
                raise _invalid()  # never advance to an unknown synchronization point
            self._final_cursor = cursor
            self._completed = True
        return ProviderPage(records=records, continuation=continuation or None)

    @staticmethod
    def _record(resource: ResourceSpec, item) -> ProviderRecord:
        if not isinstance(item, dict):
            raise _invalid()
        raw_id = item.get(resource.id_field)
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
            raise _invalid()
        stable_id = str(raw_id)
        order = None
        if resource.order_field is not None:
            order = item.get(resource.order_field)
            if order is not None and (isinstance(order, bool) or not isinstance(order, int)):
                raise _invalid()
        event_id = item.get(resource.event_field) if resource.event_field else None
        if event_id is not None and not isinstance(event_id, str):
            raise _invalid()
        deleted = item.get(resource.deleted_field) if resource.deleted_field else False
        if deleted not in (True, False, None):
            raise _invalid()
        if deleted:
            return ProviderRecord(stable_id, {}, "delete", order, event_id)
        values = item.get(resource.data_field)
        if not isinstance(values, dict):
            raise _invalid()
        return ProviderRecord(stable_id, values, "upsert", order, event_id)

    def next_cursor(self, resource_type: str, current_cursor: str | None) -> str:
        if not self._completed or self._final_cursor is None:
            raise _invalid()
        return self._final_cursor

    def close(self) -> None:
        self.session.close()

    def revalidate_credential(self) -> None:
        if self.session.credential_validator is not None:
            try:
                self.session.credential_validator()
            except (CredentialError, DataSourceCredentialError):
                raise ProviderFetchError(ProviderErrorCategory.UNAUTHORIZED) from None

    def credential_reference(self) -> dict[str, object] | None:
        value = self.session.credential_reference
        return dict(value) if isinstance(value, dict) else None
