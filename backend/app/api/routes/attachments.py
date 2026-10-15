import uuid
from pathlib import PurePath
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from app.api.deps import SessionDep, CurrentActiveUser, require_permission
from app.api.routes.workspace import checked_record
from app.models.workspace import Attachment
from app.core.config import settings
from app.crud.audit_log import log_event

router=APIRouter()
MAX_BYTES=3*1024*1024

def storage(method,path,**kwargs):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(503,"Attachment storage is not configured")
    headers={"apikey":settings.SUPABASE_SERVICE_ROLE_KEY,"Authorization":"Bearer "+settings.SUPABASE_SERVICE_ROLE_KEY,**kwargs.pop('headers',{})}
    try:
        response=httpx.request(method,settings.SUPABASE_URL.rstrip('/')+'/storage/v1'+path,headers=headers,timeout=30,**kwargs)
    except httpx.HTTPError:raise HTTPException(503,"Storage service is unavailable")
    if response.is_error:raise HTTPException(502,"Unable to complete storage operation")
    return response.json() if response.content else {}

@router.get('/attachments/config')
def config(current_user:CurrentActiveUser):
    return {"available":bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY),"max_bytes":MAX_BYTES,"types":["pdf","png","jpg","txt","csv"]}

@router.get('/records/{entity}/{record_id}/attachments')
def listing(entity:str,record_id:int,db:SessionDep,current_user:CurrentActiveUser):
    checked_record(db,entity,record_id,current_user)
    return db.scalars(select(Attachment).where(Attachment.entity==entity,Attachment.entity_id==record_id)).all()

@router.post('/records/{entity}/{record_id}/attachments')
async def upload(entity:str,record_id:int,db:SessionDep,current_user:CurrentActiveUser,file:UploadFile=File(...)):
    if current_user.role.name=='viewer':raise HTTPException(403,"Read-only access")
    checked_record(db,entity,record_id,current_user,write=True)
    content=await file.read(MAX_BYTES+1)
    if not content or len(content)>MAX_BYTES:raise HTTPException(413,"Choose a nonempty file up to 3 MB")
    ext=PurePath(file.filename or '').suffix.lower();types={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.txt':'text/plain','.csv':'text/csv'}
    if ext not in types:raise HTTPException(422,"Supported files: PDF, PNG, JPEG, TXT and CSV")
    if ext=='.pdf' and not content.startswith(b'%PDF-') or ext=='.png' and not content.startswith(b'\x89PNG\r\n\x1a\n') or ext in {'.jpg','.jpeg'} and not content.startswith(b'\xff\xd8\xff'):
        raise HTTPException(422,"File content does not match its extension")
    if ext in {'.txt','.csv'}:
        try:content.decode('utf-8')
        except UnicodeDecodeError:raise HTTPException(422,"Text files must be UTF-8")
        if b'\x00' in content:raise HTTPException(422,"Invalid text content")
    key=f'{entity}/{record_id}/{uuid.uuid4().hex}{ext}'
    storage('POST',f'/object/{settings.SUPABASE_STORAGE_BUCKET}/{key}',content=content,headers={'Content-Type':types[ext],'x-upsert':'false'})
    record=Attachment(entity=entity,entity_id=record_id,uploaded_by=current_user.id,name=PurePath(file.filename).name[:255],storage_path=key,content_type=types[ext],size=len(content))
    db.add(record);db.commit();db.refresh(record)
    log_event(db,"Attachment Uploaded",current_user.id,entity,record_id,"Private attachment uploaded")
    db.refresh(record)
    return record

@router.get('/attachments/{attachment_id}/download')
def download(attachment_id:int,db:SessionDep,current_user:CurrentActiveUser):
    record=db.get(Attachment,attachment_id)
    if not record:raise HTTPException(404,"Attachment not found")
    checked_record(db,record.entity,record.entity_id,current_user)
    result=storage('POST',f'/object/sign/{settings.SUPABASE_STORAGE_BUCKET}/{record.storage_path}',json={'expiresIn':60,'download':record.name})
    return {'url':settings.SUPABASE_URL.rstrip('/')+'/storage/v1'+result['signedURL']}

@router.delete('/attachments/{attachment_id}')
def remove(attachment_id:int,db:SessionDep,current_user:CurrentActiveUser):
    record=db.get(Attachment,attachment_id)
    if not record:raise HTTPException(404,"Attachment not found")
    if current_user.role.name=='viewer':raise HTTPException(403,"Read-only access")
    checked_record(db,record.entity,record.entity_id,current_user,write=True)
    storage('DELETE',f'/object/{settings.SUPABASE_STORAGE_BUCKET}',json={'prefixes':[record.storage_path]})
    entity,entity_id=record.entity,record.entity_id;db.delete(record);db.commit()
    log_event(db,"Attachment Deleted",current_user.id,entity,entity_id,"Private attachment deleted")
    return {'ok':True}
