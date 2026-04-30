from db_folder.db_connection import ConnectionDB
from api_folder.api_module import APIKeyManager
from pipline_folder.auth_middleware import AuthMiddleware
import json
from decimal import Decimal
from datetime import timedelta
from typing import Dict, Any, Optional

class PipelineCollector:
    def __init__(self, db_conn: ConnectionDB, auth_middleware: AuthMiddleware, api_key: str):
        self.db_conn = db_conn
        self.auth_middleware = auth_middleware
        self.api_key = api_key
    
    async def _authenticate(self) -> dict:
        """Внутренний метод для аутентификации"""
        return await self.auth_middleware.authenticate(self.api_key)
    
    async def get_pipelines(self):
        """Получить все пайплайны пользователя"""
        user = await self._authenticate()
        
        return await self.db_conn.fetch("""
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE pr.user_id = $1
            ORDER BY p.id
        """, user['id'])
    
    async def get_pipeline_by_id(self, pipeline_id: int):
        """Получить пайплайн по ID"""
        user = await self._authenticate()
        
        return await self.db_conn.fetch_one("""
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE p.id = $1 AND pr.user_id = $2
        """, pipeline_id, user['id'])
    
    async def get_structure_of_pipeline(self, pipeline_id: int):
        """Получить полную структуру пайплайна"""
        user = await self._authenticate()
        
        pipeline = await self.db_conn.fetch_one("""
            SELECT p.*, pr.name as project_name
            FROM pipelines p
            JOIN projects pr ON pr.id = p.project_id
            WHERE p.id = $1 AND pr.user_id = $2
        """, pipeline_id, user['id'])
        
        if not pipeline:
            return None
        
        nodes = await self.db_conn.fetch("""
            SELECT 
                n.*,
                nt.name as type_name,
                nt.description as type_description,
                t.id as tool_id,
                t.name as tool_name,
                t.config as tool_config
            FROM nodes n
            JOIN node_types nt ON nt.id = n.type_id
            JOIN tools t ON t.id = nt.tool_id
            WHERE n.pipeline_id = $1
            ORDER BY n.id
        """, pipeline_id)
        

        links = await self.db_conn.fetch("""
            SELECT l.*
            FROM links l
            JOIN nodes n ON n.id = l.from_node
            WHERE n.pipeline_id = $1
        """, pipeline_id)
        
        return {
            "user": dict(user),
            "pipeline": dict(pipeline),
            "nodes": [dict(n) for n in nodes],
            "links": [dict(l) for l in links],
            "statistics": {
                "total_nodes": len(nodes),
                "total_links": len(links)
            }
        }
    
    def pipeline_to_llm_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Конвертировать структуру пайплайна в JSON для LLM"""
        
        def convert_value(value):
            if isinstance(value, Decimal):
                return float(value)
            if isinstance(value, timedelta):
                return str(value)
            return value
        
        if not data:
            return {}
        
        nodes_dict = {node['id']: node for node in data['nodes']}
        
        connections = []
        for link in data['links']:
            connections.append({
                "from": nodes_dict[link['from_node']]['type_name'],
                "to": nodes_dict[link['to_node']]['type_name']
            })
        
        to_nodes = {link['to_node'] for link in data['links']}
        start_node = next((node for node in data['nodes'] if node['id'] not in to_nodes), None)
        
        execution_order = []
        current_id = start_node['id'] if start_node else None
        
        while current_id:
            node = nodes_dict[current_id]
            execution_order.append(node['type_name'])
            next_link = next((link for link in data['links'] if link['from_node'] == current_id), None)
            current_id = next_link['to_node'] if next_link else None
        
        return {
            "pipeline_name": data['pipeline']['name'],
            "description": data['pipeline']['report'],
            "blocks": [
                {
                    "name": node['type_name'],
                    "description": node['type_description'],
                    "tool": node['tool_name']
                }
                for node in data['nodes']
            ],
            "connections": connections,
            "execution_sequence": execution_order
        }
    
    async def export_pipeline_to_llm(self, pipeline_id: int) -> Optional[Dict[str, Any]]:
        """Экспортировать пайплайн в LLM-формат"""
        structure = await self.get_structure_of_pipeline(pipeline_id)
        if not structure:
            return None
        return self.pipeline_to_llm_json(structure)