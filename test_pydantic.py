from pydantic import BaseModel, field_validator
class UserCreate(BaseModel):
    username: str; password: str
    name: str = ""; phone: str = ""
    @field_validator('username','password')
    @classmethod
    def not_empty(cls,v):
        if not v or not v.strip(): raise ValueError('Required')
        return v.strip()

try:
    u = UserCreate.model_validate({"username": "Amir", "password": "123", "name": "Amir", "phone": "+998"})
    print("Success")
except Exception as e:
    print(e)
