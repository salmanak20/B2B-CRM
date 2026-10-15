"""Database-backed, process-independent fixed-window limits for auth endpoints."""
import hashlib
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.session import RateBucket
from app.core.sessions import utcnow, aware
from app.core.config import settings

def limit_auth(db, request, identifier, action="login"):
    ip = request.client.host if request.client else "unknown"
    bucket_key = hashlib.sha256(f"{action}:{ip}:{identifier.lower()}".encode()).hexdigest()
    # Also cap all identities from one source; forwarded headers are deliberately not trusted.
    for key, cap in [(bucket_key,settings.LOGIN_RATE_LIMIT),
                     (hashlib.sha256(f"{action}:{ip}".encode()).hexdigest(),settings.LOGIN_RATE_LIMIT*5)]:
        row = db.scalar(select(RateBucket).where(RateBucket.id==key).with_for_update())
        now=utcnow()
        if not row:
            row=RateBucket(id=key,count=0,window_start=now)
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                row=db.scalar(select(RateBucket).where(RateBucket.id==key).with_for_update())
        if aware(row.window_start)+timedelta(seconds=settings.RATE_WINDOW_SECONDS)<=now:
            row.count=0
            row.window_start=now
        if row.count>=cap:
            db.rollback()
            raise HTTPException(429,"Too many attempts. Please try again later.",headers={"Retry-After":str(settings.RATE_WINDOW_SECONDS)})
        row.count+=1
        db.commit()
