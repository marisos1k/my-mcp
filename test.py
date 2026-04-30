import asyncio
import json
import os
from dotenv import load_dotenv
from db_folder.db_connection import ConnectionDB
from api_folder.api_module import APIKeyManager
from pipline_folder.auth_middleware import AuthMiddleware
from pipline_folder.pipeline_collector import PipelineCollector

load_dotenv('config.env')

DB_CONFIG = {
    'user': os.getenv('user'),
    'password': os.getenv('password'),
    'database': os.getenv('database'),
    'host': os.getenv('host'),
    'port': int(os.getenv('port', 5432))
}

async def main():
    db = ConnectionDB(DB_CONFIG)
    await db.connect_db()
    
    api_manager = APIKeyManager(db)
    auth_middleware = AuthMiddleware(api_manager)
    
    # Сохраняем ключ после создания
    current_api_key = None
    
    while True:
        print("\n" + "=" * 50)
        print("🔧 КОНСОЛЬНОЕ МЕНЮ")
        print("=" * 50)
        print("1. Создать API ключ")
        print("2. Показать все пайплайны")
        print("3. Показать структуру пайплайна")
        print("4. Экспорт для LLM")
        print("5. Показать все API ключи пользователя")
        print("6. Отозвать API ключ")
        print("0. Выйти")
        print("=" * 50)
        
        choice = input("\nВыберите действие: ")
        
        # 1. Создать API ключ
        if choice == "1":
            email = input("Email пользователя: ")
            
            user = await db.fetch_one("SELECT id FROM users WHERE email = $1", email)
            if not user:
                print(f"❌ Пользователь {email} не найден")
                continue
            
            key_name = input("Название ключа: ")
            api_key = await api_manager.create_api_key(user['id'], key_name)
            
            print("\n✅ КЛЮЧ СОЗДАН!")
            print(f"🔑 {api_key}")
            print("⚠️ СОХРАНИТЕ КЛЮЧ!")
            current_api_key = api_key
        
        # 2. Показать все пайплайны
        elif choice == "2":
            if not current_api_key:
                api_key = input("Введите API ключ: ")
                current_api_key = api_key
            else:
                api_key = current_api_key
            
            collector = PipelineCollector(db, auth_middleware, api_key)
            pipelines = await collector.get_pipelines()
            
            if pipelines:
                print(f"\n📋 Найдено пайплайнов: {len(pipelines)}")
                for p in pipelines:
                    print(f"  - ID: {p['id']} | {p['name']} (проект: {p['project_name']})")
            else:
                print("❌ Нет пайплайнов или неверный ключ")
        
        # 3. Показать структуру пайплайна
        elif choice == "3":
            if not current_api_key:
                api_key = input("Введите API ключ: ")
                current_api_key = api_key
            else:
                api_key = current_api_key
            
            pipeline_id = int(input("ID пайплайна: "))
            
            collector = PipelineCollector(db, auth_middleware, api_key)
            structure = await collector.get_structure_of_pipeline(pipeline_id)
            
            if structure:
                print(f"\n📊 Пайплайн: {structure['pipeline']['name']}")
                print(f"📝 Описание: {structure['pipeline']['report']}")
                print(f"\n📦 Узлов: {len(structure['nodes'])}")
                for node in structure['nodes']:
                    print(f"  - {node['type_name']} ({node['tool_name']})")
                print(f"\n🔗 Связей: {len(structure['links'])}")
                for link in structure['links']:
                    from_node = next(n for n in structure['nodes'] if n['id'] == link['from_node'])['type_name']
                    to_node = next(n for n in structure['nodes'] if n['id'] == link['to_node'])['type_name']
                    print(f"  - {from_node} → {to_node}")
            else:
                print("❌ Пайплайн не найден")
        
        # 4. Экспорт для LLM
        elif choice == "4":
            if not current_api_key:
                api_key = input("Введите API ключ: ")
                current_api_key = api_key
            else:
                api_key = current_api_key
            
            pipeline_id = int(input("ID пайплайна: "))
            
            collector = PipelineCollector(db, auth_middleware, api_key)
            llm_data = await collector.export_pipeline_to_llm(pipeline_id)
            
            if llm_data:
                print("\n🤖 LLM ФОРМАТ:")
                print(json.dumps(llm_data, indent=2, ensure_ascii=False))
                
                # Сохранить в файл
                save = input("\nСохранить в файл? (y/n): ")
                if save.lower() == 'y':
                    filename = f"pipeline_{pipeline_id}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(llm_data, f, indent=2, ensure_ascii=False)
                    print(f"✅ Сохранен в {filename}")
            else:
                print("❌ Ошибка экспорта")
        
        # 5. Показать все ключи пользователя
        elif choice == "5":
            email = input("Email пользователя: ")
            
            user = await db.fetch_one("SELECT id FROM users WHERE email = $1", email)
            if not user:
                print(f"❌ Пользователь {email} не найден")
                continue
            
            keys = await api_manager.list_user_keys(user['id'])
            if keys:
                print(f"\n🔑 Ключи пользователя {email}:")
                for key in keys:
                    status = "✅ Активен" if key['is_active'] else "❌ Неактивен"
                    last_used = f" (последний раз: {key['last_used_at']})" if key['last_used_at'] else ""
                    print(f"  - {key['key_name']} ({key['key_prefix']}...) - {status}{last_used}")
            else:
                print("📭 Нет ключей")
        
        # 6. Отозвать API ключ
        elif choice == "6":
            email = input("Email пользователя: ")
            
            user = await db.fetch_one("SELECT id FROM users WHERE email = $1", email)
            if not user:
                print(f"❌ Пользователь {email} не найден")
                continue
            
            # Показываем активные ключи
            keys = await api_manager.list_user_keys(user['id'])
            active_keys = [k for k in keys if k['is_active']]
            
            if not active_keys:
                print("📭 Нет активных ключей")
                continue
            
            print("\nАктивные ключи:")
            for key in active_keys:
                print(f"  - {key['key_name']}")
            
            key_name = input("Название ключа для отзыва: ")
            await api_manager.revoke_api_key(user['id'], key_name)
            print(f"✅ Ключ '{key_name}' отозван")
            
            # Если отозвали текущий ключ
            if current_api_key:
                # Проверяем, не отозвали ли текущий
                user_check = await api_manager.get_user_by_api_key(current_api_key)
                if not user_check:
                    current_api_key = None
                    print("⚠️ Текущий API ключ был отозван")
        
        # 0. Выйти
        elif choice == "0":
            print("👋 До свидания!")
            break
        
        else:
            print("❌ Неверный выбор")
    
    await db.close_conn()

if __name__ == "__main__":
    asyncio.run(main())
    