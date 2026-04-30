import asyncio
import json
from typing import Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from db_folder.db_connection import ConnectionDB
from api_folder.api_module import APIKeyManager
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.pipeline_collector import PipelineCollector
from dotenv import load_dotenv
import os
import sys

load_dotenv('config.env')

DB_CONFIG = {
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database': os.getenv('database'),
    'host': os.getenv('host'),
    'port': int(os.getenv('port', 5432))
}


db = None
auth_middleware = None

async def get_collector(api_key: str) -> PipelineCollector:
    """Получить коллектор с проверкой ключа"""
    collector = PipelineCollector(db, auth_middleware, api_key)
    return collector

server = Server("pipeline-mcp-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Список доступных инструментов для LLM"""
    return [
        types.Tool(
            name="get_pipelines",
            description="Получить список всех пайплайнов пользователя",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "description": "API ключ пользователя"
                    }
                },
                "required": ["api_key"]
            }
        ),
        types.Tool(
            name="get_pipeline_structure",
            description="Получить структуру пайплайна (узлы и связи)",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string"},
                    "pipeline_id": {"type": "integer"}
                },
                "required": ["api_key", "pipeline_id"]
            }
        ),
        types.Tool(
            name="export_for_llm",
            description="Экспортировать пайплайн в формате, понятном LLM",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string"},
                    "pipeline_id": {"type": "integer"}
                },
                "required": ["api_key", "pipeline_id"]
            }
        ),
        types.Tool(
            name="get_pipeline_flow",
            description="Получить порядок выполнения узлов в пайплайне",
            inputSchema={
                "type": "object",
                "properties": {
                    "api_key": {"type": "string"},
                    "pipeline_id": {"type": "integer"}
                },
                "required": ["api_key", "pipeline_id"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Обработка вызовов инструментов"""
    
    if not arguments:
        return [types.TextContent(type="text", text="Missing arguments")]
    
    api_key = arguments.get("api_key")
    if not api_key:
        return [types.TextContent(type="text", text="API key required")]
    
    try:
        collector = await get_collector(api_key)
        
        if name == "get_pipelines":
            pipelines = await collector.get_pipelines()
            if pipelines:
                result = [dict(p) for p in pipelines]
                return [types.TextContent(
                    type="text", 
                    text=json.dumps(result, indent=2, default=str)
                )]
            else:
                return [types.TextContent(
                    type="text", 
                    text="No pipelines found or invalid API key"
                )]
        
        elif name == "get_pipeline_structure":
            pipeline_id = arguments.get("pipeline_id")
            if not pipeline_id:
                return [types.TextContent(type="text", text="pipeline_id required")]
            
            structure = await collector.get_structure_of_pipeline(pipeline_id)
            if structure:
                return [types.TextContent(
                    type="text",
                    text=json.dumps(structure, indent=2, default=str)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text="Pipeline not found or access denied"
                )]
        
        elif name == "export_for_llm":
            pipeline_id = arguments.get("pipeline_id")
            if not pipeline_id:
                return [types.TextContent(type="text", text="pipeline_id required")]
            
            llm_data = await collector.export_pipeline_to_llm(pipeline_id)
            if llm_data:
                return [types.TextContent(
                    type="text",
                    text=json.dumps(llm_data, indent=2, ensure_ascii=False)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text="Pipeline not found or access denied"
                )]
        
        elif name == "get_pipeline_flow":
            pipeline_id = arguments.get("pipeline_id")
            if not pipeline_id:
                return [types.TextContent(type="text", text="pipeline_id required")]
            
            structure = await collector.get_structure_of_pipeline(pipeline_id)
            if structure:
                flow = {
                    "pipeline": structure['pipeline']['name'],
                    "execution_sequence": []
                }
                for node in structure['nodes']:
                    flow["execution_sequence"].append({
                        "step": node['type_name'],
                        "tool": node['tool_name'],
                        "description": node['type_description']
                    })
                return [types.TextContent(
                    type="text",
                    text=json.dumps(flow, indent=2, ensure_ascii=False)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text="Pipeline not found"
                )]
        
        else:
            return [types.TextContent(
                type="text", 
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]

async def main():
    """Запуск MCP сервера"""
    global db, auth_middleware

    db = ConnectionDB(DB_CONFIG)
    await db.connect_db()
    
    api_manager = APIKeyManager(db)
    auth_middleware = AuthMiddleware(api_manager)
    
    print("MCP Pipeline Server started")
    print("Waiting for connections...")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pipeline-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())