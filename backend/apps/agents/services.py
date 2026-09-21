"""Services de résolution des demandes d'approbation (persistées en base)."""
from django.utils import timezone

from apps.sessions.models import Message

from .models import PermissionRequest


def list_pending(session_id) -> list[PermissionRequest]:
    return list(
        PermissionRequest.objects.filter(
            session_id=session_id, status=PermissionRequest.Status.PENDING
        )
    )


def respond(session_id, call_id, approved: bool) -> bool:
    """Marque une demande approuvée/refusée. Retourne False si introuvable."""
    status = (
        PermissionRequest.Status.APPROVED
        if approved
        else PermissionRequest.Status.DENIED
    )
    updated = PermissionRequest.objects.filter(
        session_id=session_id, call_id=call_id, status=PermissionRequest.Status.PENDING
    ).update(status=status, resolved_at=timezone.now())
    return updated > 0


def get_status(session_id, call_id) -> str | None:
    req = (
        PermissionRequest.objects.filter(session_id=session_id, call_id=call_id)
        .values_list("status", flat=True)
        .first()
    )
    return req


def get_or_create_user_message(session_id, run_id, content) -> tuple[Message, bool]:
    """Crée (ou retrouve, en cas de redélivraison) le message utilisateur d'un run."""
    msg = Message.objects.filter(
        session_id=session_id, role=Message.Role.USER, run_id=run_id
    ).first()
    if msg:
        return msg, False
    msg = Message.objects.create(
        session_id=session_id,
        role=Message.Role.USER,
        content=content,
        run_id=run_id,
    )
    return msg, True
