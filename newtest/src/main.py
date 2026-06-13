import asyncio
from src.config import load_config
from src.coordinator.main_coordinator import MainCoordinator
from src.parsers.marker_pdf import MarkerPDFParser
from src.knowledge.knowledge_graph import KnowledgeGraph
from src.services.rag_service import RAGService
from src.services.memory_service import MemoryService

async def main():
    """主函数"""
    print("PPT/PDF转复习提纲和考试例题智能系统")
    print("=" * 50)
    
    # 加载配置
    config = load_config()
    print(f"LLM模型: {config.llm.primary_model}")
    
    # 初始化组件
    coordinator = MainCoordinator()
    parser = MarkerPDFParser()
    knowledge_graph = KnowledgeGraph()
    rag_service = RAGService()
    memory_service = MemoryService()
    
    print("系统初始化完成")
    print("可用命令:")
    print("  /parse <file_path> - 解析文档")
    print("  /ask <question> - 提问")
    print("  /outline - 生成复习提纲")
    print("  /questions - 生成考试例题")
    print("  /quit - 退出")
    
    # 简单的命令行循环
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input == "/quit":
                print("再见！")
                break
            
            elif user_input.startswith("/parse "):
                file_path = user_input[7:].strip()
                print(f"正在解析文件: {file_path}")
                # 这里将调用解析器
                print("解析功能正在开发中...")
            
            elif user_input.startswith("/ask "):
                question = user_input[5:].strip()
                print(f"正在回答: {question}")
                # 这里将调用RAG服务
                print("问答功能正在开发中...")
            
            elif user_input == "/outline":
                print("正在生成复习提纲...")
                print("提纲生成功能正在开发中...")
            
            elif user_input == "/questions":
                print("正在生成考试例题...")
                print("例题生成功能正在开发中...")
            
            else:
                print(f"未知命令: {user_input}")
                print("输入 /help 查看可用命令")
        
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
