from fastapi import HTTPException

def sorted_query(query,model,sort_by,sort_dir):
    allowed={"id","name","title","created_at","updated_at","industry","first_name","last_name","email","status","estimated_value","value","expected_close_date"}
    if sort_by not in allowed or not hasattr(model,sort_by) or sort_dir not in {"asc","desc"}:
        raise HTTPException(422,"Unsupported sort field or direction")
    column=getattr(model,sort_by)
    return query.order_by(None).order_by(column.desc() if sort_dir=="desc" else column.asc(),model.id.asc())
