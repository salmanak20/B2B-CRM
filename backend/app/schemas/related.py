from pydantic import BaseModel, ConfigDict
class NamedUser(BaseModel):
    id:int
    name:str
    model_config=ConfigDict(from_attributes=True)
class NamedCompany(BaseModel):
    id:int
    name:str
    model_config=ConfigDict(from_attributes=True)
class NamedContact(BaseModel):
    id:int
    name:str
    model_config=ConfigDict(from_attributes=True)
