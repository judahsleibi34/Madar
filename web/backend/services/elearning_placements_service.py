"""Assessment placements reuse the existing authoring, attempt and grading engine."""
from uuid import UUID
from typing import Literal
from fastapi import HTTPException
from pydantic import Field, StrictBool
from services import elearning_assessments_service as engine
from services.elearning_structure_service import Payload
from services.elearning_settings_service import settings_available

class PlacedAssessment(engine.AssessmentCreate):
    section_id: UUID | None = None

class AttachAssessment(Payload):
    section_id: UUID | None = None
    assessment_id: UUID
    expected_revision: int = Field(ge=1,strict=True)
    required_for_completion: StrictBool = False

class PlacementCommand(Payload):
    action: Literal['duplicate','remove','restore']
    expected_revision: int = Field(ge=1,strict=True)
    confirmed: StrictBool = False


def available():
    if not settings_available(127): raise HTTPException(503,detail={'code':'assessment_upgrade_required','message':'Assessment placements require the database upgrade.'})


def listing(member,course,section=None):
    available()
    return engine.call('get_elearning_placements',member.tenant_id,p_course_id=str(course),p_section_id=str(section) if section else None)


def create(member,course,payload):
    available()
    attach=isinstance(payload,AttachAssessment)
    return engine.call('create_elearning_placed_assessment',member.tenant_id,p_course_id=str(course),p_section_id=str(payload.section_id) if payload.section_id else None,p_actor_id=member.user_id,p_expected_revision=payload.expected_revision,p_details={'required_for_completion':payload.required_for_completion} if attach else payload.assessment.model_dump(mode='json'),p_questions=[] if attach else [q.model_dump(mode='json') for q in payload.questions],p_assessment_id=str(payload.assessment_id) if attach else None)


def manage(member,course,placement,payload):
    available()
    return engine.call('manage_elearning_placement',member.tenant_id,p_course_id=str(course),p_placement_id=str(placement),p_actor_id=member.user_id,p_expected_revision=payload.expected_revision,p_action=payload.action,p_confirmed=payload.confirmed)
