from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/me", tags=["me"])

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
AVATAR_ROOT = BACKEND_ROOT / "uploads" / "avatars"
_ALLOWED = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_MAX_BYTES = 3 * 1024 * 1024


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(status_code=400, detail="Разрешены JPG, PNG, WebP")
    raw = await file.read()
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="Файл больше 3 МБ")

    AVATAR_ROOT.mkdir(parents=True, exist_ok=True)
    # Overwrite old avatar file if any.
    for ext in _ALLOWED:
        p = AVATAR_ROOT / f"{user.id}{ext}"
        if p.is_file():
            try:
                p.unlink()
            except Exception:
                pass

    dest = AVATAR_ROOT / f"{user.id}{suffix}"
    dest.write_bytes(raw)
    # Store stable public URL with cache-buster.
    user.avatar_url = f"/users/{user.id}/avatar?v={uuid.uuid4().hex[:8]}"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/avatar", response_model=UserOut)
def delete_avatar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    AVATAR_ROOT.mkdir(parents=True, exist_ok=True)
    for ext in _ALLOWED:
        p = AVATAR_ROOT / f"{user.id}{ext}"
        if p.is_file():
            try:
                p.unlink()
            except Exception:
                pass
    user.avatar_url = None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

