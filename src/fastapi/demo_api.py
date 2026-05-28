from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager

from demo_auth import register_user, login_user, get_user_by_id, db
from db_settings import config_summary
from api_folder.api_module import APIKeyManager
from graph_routes import router as graph_router
from graph_schema import ensure_graph_schema
from jwt_auth import create_token, verify_token


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await db.connect_db()
        await ensure_graph_schema()
    except Exception as e:
        print("=" * 50)
        print("ОШИБКА: не удалось подключиться к PostgreSQL")
        print(f"  {config_summary()}")
        print(f"  {type(e).__name__}: {e}")
        print()
        print("Проверьте:")
        print("  1. docker compose up db -d   (каталог my-mcp)")
        print("  2. src/fastapi/config.env — host=127.0.0.1, port как в compose")
        print("  3. Порт 5432 занят? Остановите локальный PostgreSQL или")
        print("     в compose: \"5433:5432\" и port=5433 в config.env")
        print("=" * 50)
        raise SystemExit(1) from e
    print("=" * 50)
    print("Demo API started!")
    print("URL: http://localhost:8001")
    print("Docs: http://localhost:8001/docs")
    print("=" * 50)
    yield
    await db.close_conn()


app = FastAPI(title="MCP Platform Demo", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(graph_router, prefix="/api")

# Модели
class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class CreateApiKeyRequest(BaseModel):
    key_name: str

class RevokeApiKeyRequest(BaseModel):
    key_id: int

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
    
    key_manager = APIKeyManager(db)
    raw_key = await key_manager.create_api_key(int(payload['sub']), request.key_name)
    return {"api_key": raw_key}

@app.get("/api/keys", response_model=List[ApiKeyResponse])
async def list_api_keys(token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
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


@app.post("/api/keys/revoke")
async def revoke_api_key(request: RevokeApiKeyRequest, token: str):
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    key_manager = APIKeyManager(db)
    await key_manager.revoke_api_key_by_id(int(payload["sub"]), int(request.key_id))
    return {"ok": True}

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
    