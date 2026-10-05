"""Typed, platform-neutral lesson content; mutations use the existing course lock."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import ConfigDict, Field, TypeAdapter, model_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_settings_service import settings_available
from services.elearning_structure_service import Payload, Direction, Confirmation


class TextRange(Payload):
    field: Literal['content'] = 'content'
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    fontWeight: Literal['700'] | None = None
    fontStyle: Literal['italic'] | None = None
    textDecoration: Literal['underline'] | None = None


class TextContent(Payload):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    version: Literal[1] = 1
    body: str = Field(min_length=1, max_length=50000)
    formats: list[Literal['p', 'h2', 'h3', 'bullet', 'numbered']] = Field(default_factory=list, max_length=2000)
    ranges: list[TextRange] = Field(default_factory=list, max_length=500)

    @model_validator(mode='after')
    def valid_text(self):
        if not self.body.strip():
            raise ValueError("Text content is required")
        if self.formats and len(self.formats) != len(self.body.split('\n')):
            raise ValueError('Supply one format per line')
        for span in self.ranges:
            # Browser text selections use UTF-16 offsets, shared by mobile clients.
            if span.start >= span.end or span.end > len(self.body.encode('utf-16-le')) // 2:
                raise ValueError('Invalid text selection')
        return self


class MediaContent(Payload):
    version: Literal[1] = 1
    caption: str = Field(default='', max_length=4000)


class BlockDetails(Payload):
    title: str = Field(default='', max_length=120)


class TextBlock(BlockDetails):
    type: Literal['text']
    content: TextContent


class AudioBlock(BlockDetails):
    type: Literal['audio']
    media_id: UUID
    content: MediaContent = Field(default_factory=MediaContent)


class VideoBlock(BlockDetails):
    type: Literal['video']
    media_id: UUID
    content: MediaContent = Field(default_factory=MediaContent)


BLOCK_ADAPTER = TypeAdapter(Annotated[TextBlock | AudioBlock | VideoBlock, Field(discriminator='type')])


class ContentCommand(Payload):
    action: Literal['create', 'update', 'reorder', 'duplicate', 'archive', 'restore', 'delete']
    expected_revision: int = Field(ge=1, strict=True)
    entity_id: UUID | None = None
    payload: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_payload(self):
        if (self.action == 'create') == (self.entity_id is not None):
            raise ValueError('Entity ID required only for existing blocks')
        if self.action in {'create', 'update'}:
            parsed = BLOCK_ADAPTER.validate_python(self.payload)
        else:
            parsed = (Direction if self.action == 'reorder' else Confirmation if self.action in {'delete', 'archive'} else Payload).model_validate(self.payload)
        self.payload = parsed.model_dump(mode='json', exclude_none=True)
        return self


def require_available():
    if not settings_available(123):
        raise HTTPException(503, detail={'code': 'elearning_content_upgrade_required', 'message': 'Lesson content requires the database upgrade.'})


def translate_error(error):
    if error.code == 'P0002': raise HTTPException(404, 'Lesson or block not found') from error
    if error.code == '42501': raise HTTPException(403, 'Content management access required') from error
    if error.code == 'P0001':
        code = error.message
        if code in {'elearning_content_conflict', 'elearning_content_parent_archived'}:
            raise HTTPException(409, detail={'code': code, 'message': 'Reload content before editing; archived parents cannot be edited.'}) from error
    if error.code in {'22023', '23514', '23503', '22P02'}: raise HTTPException(400, 'Invalid content or media reference') from error
    raise error


def serialize(snapshot):
    # URLs are resolved server-side from the registry, never from block payloads.
    if snapshot is None:
        raise HTTPException(404, "Lesson not found")
    return snapshot


def get_content(tenant_id, course_id, lesson_id):
    require_available()
    try:
        return serialize(service_supabase.rpc('get_elearning_content', {
            'p_tenant_id': tenant_id, 'p_course_id': str(course_id), 'p_lesson_id': str(lesson_id),
        }).execute().data)
    except APIError as error: translate_error(error)


def execute_command(tenant_id, course_id, lesson_id, user_id, command):
    require_available()
    try:
        return serialize(service_supabase.rpc('manage_elearning_content', {
            'p_tenant_id': tenant_id, 'p_course_id': str(course_id), 'p_lesson_id': str(lesson_id),
            'p_user_id': user_id, 'p_expected_revision': command.expected_revision,
            'p_action': command.action, 'p_entity_id': str(command.entity_id) if command.entity_id else None,
            'p_payload': command.payload,
        }).execute().data)
    except APIError as error: translate_error(error)
