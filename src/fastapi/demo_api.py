from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import jwt
from datetime import datetime, timedelta
import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from demo_auth import register_user, login_user, get_user_by_id, db
from api_folder.api_module import APIKeyManager
from pipline_folder.pipeline_collector import PipelineCollector
from pipline_folder.auth_middleware import AuthMiddleware

app = FastAPI(title="MCP Platform Demo", port=8001)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# JWT настройки
SECRET_KEY = "demo_secret_key_2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# Модели
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class CreateApiKeyRequest(BaseModel):
    key_name: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str

class ApiKeyResponse(BaseModel):
    id: int
    key_name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

def create_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        return None

# ============ РЕГИСТРАЦИЯ ============
@app.get("/")
async def root():
    return {"message": "MCP Platform Demo API", "docs": "/docs"}

@app.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    user, error = await register_user(request.email, request.password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    token = create_token(user['id'], user['email'])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user['id'],
        "email": user['email']
    }

@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    user, error = await login_user(request.email, request.password)
    if error:
        raise HTTPException(status_code=401, detail=error)
    token = create_token(user['id'], user['email'])
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user['id'],
        "email": user['email']
    }

@app.get("/auth/me")
async def get_me(token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await get_user_by_id(int(payload['sub']))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user['id'], "email": user['email']}

@app.post("/api/keys")
async def create_api_key(request: CreateApiKeyRequest, token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    await db.connect_db()
    key_manager = APIKeyManager(db)
    raw_key = await key_manager.create_api_key(int(payload['sub']), request.key_name)
    return {"api_key": raw_key}

@app.get("/api/keys", response_model=List[ApiKeyResponse])
async def list_api_keys(token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    await db.connect_db()
    key_manager = APIKeyManager(db)
    keys = await key_manager.list_user_keys(int(payload['sub']))
    
    result = []
    for key in keys:
        result.append({
            "id": key['id'],
            "key_name": key['key_name'],
            "key_prefix": key['key_prefix'],
            "is_active": key['is_active'],
            "created_at": key['created_at'],
            "last_used_at": key['last_used_at']
        })
    return result

# ============ ПРОЕКТЫ ============

@app.get("/api/projects")
async def get_projects(token: str):
    """Получить список проектов пользователя"""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = int(payload['sub'])
    
    # Убираем created_at, если его нет в таблице
    projects = await db.fetch(
        """
        SELECT id, name 
        FROM projects 
        WHERE user_id = $1 
        ORDER BY id DESC
        """,
        user_id
    )
    
    return [dict(p) for p in projects]

@app.post("/api/projects")
async def create_project(name: str, token: str):
    """Создать новый проект"""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = int(payload['sub'])
    
    # Проверяем, нет ли проекта с таким именем
    existing = await db.fetch_one(
        "SELECT id FROM projects WHERE user_id = $1 AND name = $2",
        user_id, name
    )
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")
    
    await db.execute(
        """
        INSERT INTO projects (user_id, name) 
        VALUES ($1, $2)
        """,
        user_id, name
    )
    
    project = await db.fetch_one(
        "SELECT id, name FROM projects WHERE user_id = $1 AND name = $2",
        user_id, name
    )
    
    return dict(project)

@app.get("/api/projects/{project_id}/pipelines")
async def get_pipelines(project_id: int, token: str):
    """Получить все пайплайны в проекте"""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = int(payload['sub'])
    
    # Проверяем, что проект принадлежит пользователю
    project = await db.fetch_one(
        "SELECT id FROM projects WHERE id = $1 AND user_id = $2",
        project_id, user_id
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Получаем пайплайны
    pipelines = await db.fetch(
        """
        SELECT id, name, report, max_time, max_cost, max_fail_percent, score
        FROM pipelines 
        WHERE project_id = $1 
        ORDER BY id DESC
        """,
        project_id
    )
    
    return [dict(p) for p in pipelines]

@app.get("/api/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: int, token: str):
    """Получить детальную информацию о пайплайне"""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = int(payload['sub'])
    
    # Получаем пайплайн с проверкой прав через проект
    pipeline = await db.fetch_one(
        """
        SELECT p.*, pr.name as project_name, pr.id as project_id
        FROM pipelines p
        JOIN projects pr ON pr.id = p.project_id
        WHERE p.id = $1 AND pr.user_id = $2
        """,
        pipeline_id, user_id
    )
    
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return dict(pipeline)

@app.on_event("startup")
async def startup():
    await db.connect_db()
    print("=" * 50)
    print("Demo API started!")
    print(f"URL: http://localhost:8001")
    print(f"Docs: http://localhost:8001/docs")
    print("=" * 50)

@app.on_event("shutdown")
async def shutdown():
    await db.close_conn()



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
    