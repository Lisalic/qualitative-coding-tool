from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.api.utils import get_user_id_from_request
from backend.app.database import get_db, Prompt, User

router = APIRouter()


@router.get("/prompts/")
def list_prompts(request: Request, prompt_type: str = None, db: Session = Depends(get_db)):
    """List user's prompts."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    q = db.query(Prompt).filter(Prompt.user_id == user_id)

    if prompt_type:
        q = q.filter(Prompt.type == prompt_type)

    rows = q.all()
    result = []
    for r in rows:
        result.append({
            "id": int(r.id),
            "user_id": str(r.user_id) if r.user_id is not None else None,
            "promptname": r.promptname,
            "prompt": r.prompt,
            "type": r.type,
        })

    return JSONResponse({"prompts": result})


@router.post("/prompts/")
async def create_prompt(request: Request, db: Session = Depends(get_db)):
    """Create a new prompt."""
    content_type = (request.headers.get("content-type") or "").lower()
    data = {}
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            # convert FormData to a simple dict
            data = {k: form.get(k) for k in form.keys()}
    except Exception:
        data = {}

    display_name = data.get("display_name") or data.get("promptname")
    prompt_val = data.get("prompt")
    ptype = data.get("type")
    user_id = data.get("user_id")

    if not display_name or not prompt_val or not ptype:
        raise HTTPException(status_code=400, detail="Missing required fields: display_name, prompt, type")

    if not user_id:
        try:
            # Inline the me logic
            user_id_from_request = get_user_id_from_request(request)
            if not user_id_from_request:
                raise HTTPException(status_code=401, detail="Not authenticated")

            user = db.query(User).filter(User.id == user_id_from_request).first()
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            user_id = str(user.id)
        except HTTPException as he:
            raise he
        except Exception:
            raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    new = Prompt(user_id=uid, promptname=display_name, prompt=prompt_val, type=ptype)
    db.add(new)
    try:
        db.commit()
        db.refresh(new)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"id": int(new.id), "user_id": str(new.user_id), "promptname": new.promptname, "prompt": new.prompt, "type": new.type})


@router.post("/prompts/{prompt_id}/update")
async def update_prompt(prompt_id: int, request: Request, db: Session = Depends(get_db)):
    """Update a prompt."""
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""

    content_type = (request.headers.get("content-type") or "").lower()
    data = {}
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            # convert FormData to a simple dict
            data = {k: form.get(k) for k in form.keys()}
    except Exception:
        data = {}

    display_name = data.get("display_name") or data.get("promptname")
    prompt_val = data.get("prompt")
    ptype = data.get("type")

    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    p = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")

    try:
        owner_id = int(p.user_id)
    except Exception:
        owner_id = p.user_id
    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    if owner_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    # accept either `display_name` (legacy) or `promptname` (canonical)
    new_name = display_name
    if new_name is not None:
        p.promptname = new_name
    if prompt_val is not None:
        p.prompt = prompt_val
    if ptype is not None:
        p.type = ptype

    try:
        db.commit()
        db.refresh(p)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"id": int(p.id), "user_id": str(p.user_id), "promptname": p.promptname, "prompt": p.prompt, "type": p.type})


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, request: Request, db: Session = Depends(get_db)):
    """Delete a prompt owned by the authenticated user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    p = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # ensure ownership: Prompt.user_id should be UUID referencing User.id
    try:
        owner_id = str(p.user_id) if p.user_id is not None else None
    except Exception:
        owner_id = p.user_id
    try:
        uid = int(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id in token")

    if owner_id != str(uid):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        db.delete(p)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"deleted": True, "id": int(p.id)})