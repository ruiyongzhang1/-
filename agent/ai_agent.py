import warnings
import os
import asyncio
import time
import traceback
import concurrent.futures
from typing import Dict, Any, List, Optional, Generator
from agent.RAG.retriever import rag_search
from agent.sql.attraction_ezqa_service import myanswer
from agent.shared_cache import INFO_CACHE
# 抑制LangChain弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage, BaseMessage
from dotenv import load_dotenv

# MCP 工具导入
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools
    from langgraph.prebuilt import create_react_agent
    MCP_AVAILABLE = True
except ImportError:
    print("MCP工具不可用，将使用备用模式")
    MCP_AVAILABLE = False

# PDF生成类和提示词导入
from agent.pdf_generator import PDFGeneratorTool
try:
    from .prompts import (
        GENERAL_SYSTEM_PROMPT, TRAVEL_SYSTEM_PROMPT, PDF_PROMPT,
        INFORMATION_COLLECTOR_PROMPT, ITINERARY_PLANNER_PROMPT
    )
    from .redis_memory import get_redis_memory_manager, SimpleMemory as RedisSimpleMemory
except ImportError:
    from agent.prompts import (
        GENERAL_SYSTEM_PROMPT, TRAVEL_SYSTEM_PROMPT, PDF_PROMPT,
        INFORMATION_COLLECTOR_PROMPT, ITINERARY_PLANNER_PROMPT
    )
    from agent.redis_memory import get_redis_memory_manager, SimpleMemory as RedisSimpleMemory

# =============================================================================
# 1. Component and Utility Classes (The Foundation)
# 这些是构成系统的基础模块，每个类职责单一。
# =============================================================================



class ConfigManager:
    """统一配置管理"""
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_API_URL")
        self.searchapi_key = os.getenv("SEARCHAPI_API_KEY", "")
        self.mcp_server_path = "agent/mcp_server.py"
        
        if not self.api_key:
            raise ValueError("未配置OpenAI API密钥")
    
    def get_server_params(self) -> StdioServerParameters:
        """获取MCP服务器参数"""
        return StdioServerParameters(
            command="python",
            args=[self.mcp_server_path],
            env={"SEARCHAPI_API_KEY": self.searchapi_key}
        )

class LLMFactory:
    """LLM实例工厂"""
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def create_llm(self, model: str = "gpt-4.1", temperature: float = 0.8, 
                   streaming: bool = False) -> ChatOpenAI:
        """创建LLM实例"""
        return ChatOpenAI(
            api_key=self.config.api_key,
            model=model,
            base_url=self.config.base_url,
            temperature=temperature,
            streaming=streaming
        )

class MCPManager:
    """MCP连接和工具管理"""
    def __init__(self, config: ConfigManager):
        self.config = config
        self.mcp_client = None
    
    async def load_tools_async(self) -> List[Any]:
        """异步加载MCP工具 - 使用官方langchain-mcp-adapters方法"""
        try:
            # 方法1：使用 MultiServerMCPClient 连接本地MCP服务器
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain_mcp_adapters.tools import load_mcp_tools
            
            # 创建MCP客户端配置
            server_config = {
                "travel_tools": {
                    "command": "python",
                    "args": [self.config.mcp_server_path],
                    "transport": "stdio",
                    "env": {
                        "SEARCHAPI_API_KEY": self.config.searchapi_key,
                        "MCP_TRANSPORT": "stdio"
                    }
                }
            }
            
            print("🔧 [MCP] 正在使用 MultiServerMCPClient 连接到本地MCP服务器...")
            self.mcp_client = MultiServerMCPClient(server_config)
            
            try:
                # 加载工具
                tools = await self.mcp_client.get_tools()
                print(f"✅ [MCP] 成功加载了 {len(tools)} 个MCP工具")
                
                # 打印工具详情
                for i, tool in enumerate(tools):
                    print(f"  工具 {i+1}: {tool.name} - {tool.description}")
                
                return tools
                
            except Exception as e:
                print(f"❌ [MCP] MultiServerMCPClient 连接失败: {e}")
                print("🔄 [MCP] 回退到直接导入模式...")
                return await self._load_tools_direct()
                
        except ImportError as e:
            print(f"❌ [MCP] langchain-mcp-adapters 不可用: {e}")
            print("🔄 [MCP] 回退到直接导入模式...")
            return await self._load_tools_direct()
        except Exception as e:
            print(f"❌ [MCP] 加载工具时发生错误: {e}")
            print("🔄 [MCP] 回退到直接导入模式...")
            return await self._load_tools_direct()
    
    async def _load_tools_direct(self) -> List[Any]:
        """直接导入MCP工具的备用方法"""
        try:
            # 直接导入本地MCP工具，返回完整的JSON结果
            from agent.mcp_server import (
                get_current_time, search_google, search_google_maps, 
                search_google_flights, search_google_hotels
            )
            from langchain.tools import tool
            import json
            
            # 创建LangChain工具包装器，返回详细的搜索结果
            tools = []
            
            # 包装get_current_time - 返回完整结果
            @tool
            async def get_current_time_tool(format: str = "iso", days_offset: str = "0", 
                                          return_future_dates: str = "false", future_days: str = "7") -> str:
                """获取当前系统时间和旅行日期建议"""
                result = await get_current_time(format=format, days_offset=days_offset, 
                                              return_future_dates=return_future_dates, future_days=future_days)
                # 返回格式化的JSON字符串，便于前端显示
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            # 包装search_google - 返回完整结果
            @tool
            async def search_google_tool(q: str, location: str = None, gl: str = "cn", 
                                       hl: str = "zh-cn", num: str = "10") -> str:
                """搜索Google搜索结果，返回完整的搜索结果包括有机结果、知识图谱、相关问题等"""
                result = await search_google(q=q, location=location, gl=gl, hl=hl, num=num)
                
                # 如果有错误，返回错误信息
                if isinstance(result, dict) and "error" in result:
                    return f"搜索失败: {result['error']}"
                
                # 返回完整的搜索结果，包含所有API返回的数据
                search_info = {
                    "query": q,
                    "search_metadata": result.get("search_metadata", {}),
                    "organic_results": result.get("organic_results", []),
                    "knowledge_graph": result.get("knowledge_graph", {}),
                    "answer_box": result.get("answer_box", {}),
                    "related_questions": result.get("related_questions", []),
                    "local_results": result.get("local_results", [])
                }
                
                return json.dumps(search_info, ensure_ascii=False, indent=2)
            
            # 包装search_google_maps - 返回完整结果
            @tool
            async def search_google_maps_tool(query: str, location_ll: str = None) -> str:
                """搜索Google地图上的地点或服务，返回完整的地图搜索结果"""
                result = await search_google_maps(query=query, location_ll=location_ll)
                
                # 如果有错误，返回错误信息
                if isinstance(result, dict) and "error" in result:
                    return f"地图搜索失败: {result['error']}"
                
                # 返回完整的地图搜索结果
                map_info = {
                    "query": query,
                    "search_metadata": result.get("search_metadata", {}),
                    "local_results": result.get("local_results", []),
                    "place_results": result.get("place_results", {}),
                    "related_places": result.get("related_places", [])
                }
                
                return json.dumps(map_info, ensure_ascii=False, indent=2)
            
            # 包装search_google_flights - 返回完整结果
            @tool
            async def search_google_flights_tool(departure_id: str, arrival_id: str, outbound_date: str, 
                                               flight_type: str = "round_trip", return_date: str = None,
                                               adults: str = "1", currency: str = "CNY") -> str:
                """搜索Google航班信息，返回完整的航班搜索结果"""
                # 自动处理日期
                from datetime import datetime, timedelta
                today = datetime.now()
                
                if not outbound_date:
                    outbound_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                else:
                    try:
                        outbound = datetime.strptime(outbound_date, "%Y-%m-%d")
                        if outbound.date() < today.date():
                            outbound_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                    except ValueError:
                        outbound_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
                
                if flight_type == "round_trip" and not return_date:
                    return_date = (today + timedelta(days=14)).strftime("%Y-%m-%d")
                
                result = await search_google_flights(
                    departure_id=departure_id,
                    arrival_id=arrival_id,
                    outbound_date=outbound_date,
                    flight_type=flight_type,
                    return_date=return_date,
                    adults=adults,
                    currency=currency
                )
                
                # 如果有错误，返回错误信息
                if isinstance(result, dict) and "error" in result:
                    return f"航班搜索失败: {result['error']}"
                
                # 返回完整的航班搜索结果
                flight_info = {
                    "search_parameters": {
                        "departure_id": departure_id,
                        "arrival_id": arrival_id,
                        "outbound_date": outbound_date,
                        "return_date": return_date,
                        "adults": adults,
                        "currency": currency
                    },
                    "search_metadata": result.get("search_metadata", {}),
                    "best_flights": result.get("best_flights", []),
                    "other_flights": result.get("other_flights", []),
                    "price_insights": result.get("price_insights", {}),
                    "airports": result.get("airports", [])
                }
                
                return json.dumps(flight_info, ensure_ascii=False, indent=2)
            
            # 包装search_google_hotels - 返回完整结果
            @tool
            async def search_google_hotels_tool(q: str, check_in_date: str = None, check_out_date: str = None,
                                              adults: str = "1", currency: str = "CNY") -> str:
                """搜索Google酒店信息，返回完整的酒店搜索结果"""
                # 自动处理日期
                from datetime import datetime, timedelta
                today = datetime.now()
                
                if not check_in_date:
                    check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                if not check_out_date:
                    check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                
                # 验证日期
                try:
                    check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
                    if check_in.date() < today.date():
                        check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                        check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                except ValueError:
                    check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                    check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                
                result = await search_google_hotels(
                    q=q,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date,
                    adults=adults,
                    currency=currency
                )
                
                # 如果有错误，返回错误信息
                if isinstance(result, dict) and "error" in result:
                    return f"酒店搜索失败: {result['error']}"
                
                # 返回完整的酒店搜索结果
                hotel_info = {
                    "search_parameters": {
                        "location": q,
                        "check_in_date": check_in_date,
                        "check_out_date": check_out_date,
                        "adults": adults,
                        "currency": currency
                    },
                    "search_metadata": result.get("search_metadata", {}),
                    "properties": result.get("properties", []),
                    "brands": result.get("brands", []),
                    "property_types": result.get("property_types", []),
                    "filters": result.get("filters", {})
                }
                
                return json.dumps(hotel_info, ensure_ascii=False, indent=2)
            
            tools = [
                get_current_time_tool,
                search_google_tool,
                search_google_maps_tool,
                search_google_flights_tool,
                search_google_hotels_tool
            ]
            
            print(f"✅ [MCP] 直接导入模式：加载了 {len(tools)} 个本地MCP工具（返回完整API响应）")
            return tools
            
        except Exception as e:
            print(f"❌ [MCP] 直接导入模式也失败: {e}")
            return []
    
    def load_tools_sync(self) -> List[Any]:
        """同步加载MCP工具的包装器"""
        try:
            # 使用AsyncSyncWrapper来避免事件循环问题
            tools = AsyncSyncWrapper.run_async_in_thread(self.load_tools_async)
            print(f"[DEBUG] MCPManager.load_tools_sync() 返回的tools:")
            for idx, tool in enumerate(tools):
                print(f"  Tool {idx}: type={type(tool)}, name={getattr(tool, 'name', None)}, desc={getattr(tool, 'description', None)}, args_schema={getattr(tool, 'args_schema', None)}")
            return tools
        except Exception as e:
            print(f"同步加载MCP工具失败: {e}")
            return []

class AsyncSyncWrapper:
    """异步同步转换工具"""
    @staticmethod
    def run_async_in_thread(async_func_or_coro, timeout: int = 1200):
        """在线程池中运行异步函数或协程"""
        def sync_wrapper():
            if callable(async_func_or_coro):
                # 如果是函数，调用它来获得协程
                coro = async_func_or_coro()
            else:
                # 如果已经是协程，直接使用
                coro = async_func_or_coro
            return asyncio.run(coro)
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(sync_wrapper)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"⚠️ [超时错误] 异步任务执行超时 ({timeout}秒)，正在返回默认响应")
                return "信息收集超时，请稍后重试或检查网络连接。"

class StreamingUtils:
    """流式输出工具"""
    @staticmethod
    def stream_text(text: str, chunk_size: int = 50) -> Generator[str, None, None]:
        """将文本分块进行流式输出"""
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]

class ResponseExtractor:
    """响应内容提取工具"""
    @staticmethod
    def extract_agent_response(response: Dict[str, Any]) -> str:
        """从LangGraph智能体响应中提取内容"""
        if response and "messages" in response:
            last_message = response["messages"][-1]
            if hasattr(last_message, 'content'):
                return last_message.content
            elif isinstance(last_message, dict) and 'content' in last_message:
                return last_message['content']
        return "抱歉，未能获取到有效响应。"

# =============================================================================
# 2. Refactored Agent Classes (The Workers)
# 每个智能体类现在通过构造函数接收其依赖项（如LLM实例和工具），而不是自己创建。
# This is called Dependency Injection.
# =============================================================================

class InformationCollectorAgent:
    """信息收集智能体（绑定MCP工具）"""
    def __init__(self, llm: ChatOpenAI, tools: List[Any]):
        self.llm = llm
        self.tools = tools
        self.agent = create_react_agent(self.llm, self.tools) if self.tools else None
        print(f"信息收集智能体已创建，可用工具数量: {len(self.tools)}")
    
    async def collect_information_async(self, user_request: str) -> str:
        if not self.agent:
            return f"信息收集智能体不可用（工具加载失败），无法处理请求: {user_request}"
        
        # print(f"\n🔍 [MCP调试] 开始信息收集，用户请求: {user_request}")
        print(f"🔧 [MCP调试] 可用工具数量: {len(self.tools)}")

        collector_request = f"{INFORMATION_COLLECTOR_PROMPT}\n用户需求:{user_request}"
        
        print(f"📝 [MCP调试] 发送给智能体的提示词长度: {len(collector_request)} 字符")
        
        try:
            print(f"🚀 [MCP调试] 开始调用智能体，预计会使用MCP工具进行搜索...")
            # 使用正确的LangGraph 0.5.2 API格式
            from langchain.schema import HumanMessage
            response = await self.agent.ainvoke({"messages": [HumanMessage(content=collector_request)]})
            
            # 提取响应内容
            response_content = ResponseExtractor.extract_agent_response(response)
            
            print(f"✅ [MCP调试] 信息收集完成，响应长度: {len(response_content)} 字符")
            print(f"📊 [MCP调试] 完整响应内容: {response_content}")
            
            # 确保响应内容不为空
            if not response_content or len(response_content.strip()) < 20:
                print("⚠️  [MCP调试] 响应内容过短，可能出现问题")
                return "信息收集完成，但响应内容异常短，请检查系统状态。"
            
            return response_content
            
        except Exception as e:
            print(f"❌ [MCP调试] 信息收集过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return f"信息收集失败: {str(e)}"
    def collect_information(self, user_request: str) -> str:  # noqa: D401
        """Collect information **synchronously** and return **plain text** only."""
        return AsyncSyncWrapper.run_async_in_thread(
            lambda: self.collect_information_async(user_request)
        )

    def get_response_stream_with_frontend(self, message: str):
        """把收集结果以 dict 形式首发，留给上层包装"""
        try:
            full_response = AsyncSyncWrapper.run_async_in_thread(
                lambda: self.collect_information_async(message)
            )
            if not full_response:
                full_response = "信息收集完成，但内容为空。"
            # 直接返回 Python dict，不再自己 json.dumps
            
            yield {"info_collection_result": full_response}
            return full_response
        except Exception as e:
            yield {"info_collection_result": f"信息收集失败: {e}"}
            return f"信息收集失败: {e}"
        
    def get_response_stream(self, message: str):
        """获取响应流"""
        try:
            full_response = AsyncSyncWrapper.run_async_in_thread(
                lambda: self.collect_information_async(message)
            )
            
            # 确保响应不为空或只是错误信息
            if not full_response or full_response.startswith("处理请求时出现错误:"):
                print(f"⚠️  [信息收集] 响应为空或包含错误，尝试返回基本信息")
                full_response = f"已收到您的旅行规划请求：{message}。正在为您准备详细的旅行信息..."
            
            yield from StreamingUtils.stream_text(full_response)
        except Exception as e:
            error_msg = f"信息收集过程中出现错误: {str(e)}"
            print(f"❌ [信息收集] {error_msg}")
            yield error_msg

class PlannerAgent:
    """行程规划智能体"""
    def __init__(self, llm_streaming: ChatOpenAI, llm_normal: ChatOpenAI):
        self.llm_streaming = llm_streaming
        self.llm_normal = llm_normal
        print("行程规划智能体已创建")
        
    def get_response_stream(self, message: str, collected_info: str = "", conversation_history: list = None, raw_mcp_results: dict = None):
        """获取真流式响应（支持对话记忆和原始MCP数据）"""
        # 构建规划请求内容
        if collected_info:
            planning_content = f"用户原始需求：\n{message}\n\n信息收集智能体提供的详细信息：\n{collected_info}"
        else:
            planning_content = f"用户需求：\n{message}"
        
        # 添加RAG搜索结果
        planning_content = planning_content + rag_search(message, top_k=3)['context']
        
        # 如果有原始MCP数据，添加到规划内容中
        if raw_mcp_results:
            planning_content += "\n\n=== 重要：原始API搜索结果 ===\n"
            planning_content += "**请严格基于以下真实API数据进行规划，不要生成虚假信息：**\n\n"
            
            for data_type, raw_data in raw_mcp_results.items():
                planning_content += f"\n### {data_type.upper()}原始数据:\n{raw_data}\n"
            
            planning_content += "\n**重要提醒：请严格使用上述真实API数据中的具体信息（如航班号、价格、酒店名称等），不要编造任何虚假信息。**\n"
            
            print(f"📊 [旅行规划] 已添加原始MCP数据到规划内容，类型: {list(raw_mcp_results.keys())}")
        else:
            print("⚠️  [旅行规划] 未收到原始MCP数据，将基于已有信息进行规划")
        
        # 构建包含历史记忆的消息列表
        messages = [SystemMessage(content=ITINERARY_PLANNER_PROMPT)]
        
        # 添加历史对话记忆（关于旅行规划的上下文）
        if conversation_history:
            for msg in conversation_history[-8:]:  # 旅行规划可能需要更多上下文，但控制数量
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role == 'user':
                    messages.append(HumanMessage(content=content))
                elif role == 'assistant':
                    messages.append(AIMessage(content=content))
        
        # 添加当前规划请求
        messages.append(HumanMessage(content=planning_content))
        
        # 真流式调用LLM
        for chunk in self.llm_streaming.stream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content

class PdfAgent:
    """PDF生成智能体"""
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.pdf_generator = PDFGeneratorTool()
        print("PDF生成智能体已创建")

    def generate_pdf(self, user_request: str, conversation_history: list = None) -> str:
        """生成PDF旅游攻略"""
        if not conversation_history:
            return "暂无对话历史记录，无法生成PDF报告。"
        
        conversation_text = self._format_conversation_history(conversation_history)
        # summary = self._generate_conversation_summary(conversation_text, user_request)
        detailed_guide = self._generate_travel_guide(conversation_text, user_request)
        full_content = f"# 旅行对话记录\n\n{conversation_text}\n\n---\n\n# 详细旅游攻略\n\n{detailed_guide}"
        # pdf_result = self.pdf_generator.generate_travel_pdf(conversation_data=full_content, summary=summary, user_info="user") # user_info can be enhanced
        pdf_result = self.pdf_generator.generate_travel_pdf(conversation_data=full_content, summary=detailed_guide, user_info="user") # user_info can be enhanced
        return f"📄{pdf_result}"
    
    def _format_conversation_history(self, conversation_history: list) -> str:
        return "\n\n".join([f"**{msg.get('role', '未知')}**: {msg.get('content', '')}" for msg in conversation_history])

    def _generate_conversation_summary(self, conversation_text: str, user_request: str) -> str:
        prompt = f"请对以下旅行对话进行总结，提取关键信息：\n{conversation_text}\n当前请求：{user_request}\n总结应简洁明了，不超过200字。"
        response = self.llm.invoke([SystemMessage(content="你是一个专业的旅行顾问，擅长总结和提炼信息。"), HumanMessage(content=prompt)])
        return response.content
        
    def _generate_travel_guide(self, conversation_text: str, user_request: str) -> str:
        prompt = f"基于以下对话内容，生成一份详细的旅游攻略：\n{conversation_text}\n当前需求:{user_request}\n请生成一份完整的旅游攻略,使用能让pdfkit渲染的markdown格式。"
        response = self.llm.invoke([SystemMessage(content=PDF_PROMPT), HumanMessage(content=prompt)])
        return response.content
    
    def get_response_stream(self, message: str, conversation_history: list):
        """获取响应流"""
        full_response = self.generate_pdf(message, conversation_history)
        yield from StreamingUtils.stream_text(full_response)

class NormalAgent:
    """普通对话智能体"""
    def __init__(self, llm_streaming: ChatOpenAI):
        self.llm_streaming = llm_streaming
        print("普通对话智能体已创建")

    def get_response_stream(self, message: str, conversation_history: list = None):
        """获取真流式响应（支持对话记忆）"""
        # 构建包含历史记忆的消息列表
        messages = [SystemMessage(content=GENERAL_SYSTEM_PROMPT)]
        
        # 添加历史对话记忆
        if conversation_history:
            for msg in conversation_history[-10:]:  # 只取最近10条消息避免token过多
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role == 'user':
                    messages.append(HumanMessage(content=content))
                elif role == 'assistant':
                    messages.append(AIMessage(content=content))
        
        # 添加当前用户消息
        messages.append(HumanMessage(content=message))
        
        # 流式生成响应
        for chunk in self.llm_streaming.stream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content

# =============================================================================
# 3. AgentService (The Conductor)
# 这是一个新的核心类，负责所有组件的初始化、管理和协同工作。
# =============================================================================

class AgentService:
    """智能体服务的中央协调器（懒加载模式）"""
    def __init__(self, redis_config=None):
        print("初始化 AgentService...")
        self.config = ConfigManager()
        self.llm_factory = LLMFactory(self.config)
        self.mcp_manager = MCPManager(self.config)
        
        # 懒加载：不在初始化时立即加载MCP工具
        self._mcp_tools = None
        self._tools_loaded = False
        
        # 初始化Redis记忆管理器
        if redis_config is None:
            redis_config = {}
        self.redis_memory_manager = get_redis_memory_manager(**redis_config)
        
        self.agent_sessions: Dict[str, Dict[str, Any]] = {}
        print("AgentService 初始化完成（使用懒加载模式 + Redis记忆）。")

    @property
    def mcp_tools(self) -> List[Any]:
        """懒加载MCP工具"""
        if not self._tools_loaded:
            print("首次请求MCP工具，开始加载...")
            self._mcp_tools = self.mcp_manager.load_tools_sync()
            self._tools_loaded = True
            print(f"MCP工具加载完成，共 {len(self._mcp_tools)} 个工具")
        return self._mcp_tools

    def _create_agent_session(self, user_email: str, conv_id: str) -> Dict[str, Any]:
        """为新用户创建一套完整的智能体和记忆"""
        print(f"为用户 {user_email} 创建新的智能体 Session...")
        llm_normal = self.llm_factory.create_llm(streaming=False)
        llm_streaming = self.llm_factory.create_llm(streaming=True)
        
        # 创建会话特定的记忆
        session_key = f"{user_email}_{conv_id}"
        memory = RedisSimpleMemory(session_key, self.redis_memory_manager)
        
        return {
            'collector': InformationCollectorAgent(llm_normal, self.mcp_tools),  # 这里才会触发工具加载
            'planner': PlannerAgent(llm_streaming, llm_normal),
            'pdf_agent': PdfAgent(llm_normal),
            'normal_agent': NormalAgent(llm_streaming),
            'memory': memory,
        }

    
    def _get_city_code(self, city_name: str) -> str:
        """获取城市的机场代码"""
        # 常见城市代码映射
        city_codes = {
            "上海": "SHA", "北京": "PEK", "广州": "CAN", "深圳": "SZX",
            "成都": "CTU", "杭州": "HGH", "西安": "XIY", "重庆": "CKG",
            "南京": "NKG", "武汉": "WUH", "青岛": "TAO", "大连": "DLC",
            "厦门": "XMN", "昆明": "KMG", "长沙": "CSX", "郑州": "CGO"
        }
        
        for city, code in city_codes.items():
            if city in city_name:
                return code
        
        # 如果找不到匹配的城市，返回默认值
        return "SHA" if "上海" in city_name else "PEK"
    
    def _extract_departure_id(self, message: str) -> str:
        """从消息中提取出发地代码"""
        # 常见城市代码映射
        city_codes = {
            "上海": "SHA", "北京": "PEK", "广州": "CAN", "深圳": "SZX",
            "成都": "CTU", "杭州": "HGH", "西安": "XIY", "重庆": "CKG"
        }
        
        for city, code in city_codes.items():
            if city in message and ("出发" in message or "从" in message):
                return code
        
        return "SHA"  # 默认上海
    
    def _extract_arrival_id(self, message: str) -> str:
        """从消息中提取目的地代码"""
        # 常见城市代码映射
        city_codes = {
            "上海": "SHA", "北京": "PEK", "广州": "CAN", "深圳": "SZX",
            "成都": "CTU", "杭州": "HGH", "西安": "XIY", "重庆": "CKG"
        }
        
        for city, code in city_codes.items():
            if city in message and ("目的地" in message or "到" in message or "去" in message):
                return code
        
        return "PEK"  # 默认北京
    
    def _extract_destination(self, message: str) -> str:
        """从消息中提取目的地名称"""
        # 从消息中提取目的地
        destinations = ["北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆"]
        
        for dest in destinations:
            if dest in message:
                return dest
        
        return "北京"  # 默认北京
    
    def _extract_outbound_date(self, message: str) -> str:
        """从消息中提取出发日期"""
        # 简化实现，返回明天
        from datetime import datetime, timedelta
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    
    def _extract_return_date(self, message: str) -> str:
        """从消息中提取返回日期"""
        # 简化实现，返回一周后
        from datetime import datetime, timedelta
        next_week = datetime.now() + timedelta(days=7)
        return next_week.strftime("%Y-%m-%d")

    def get_or_create_agent_session(self, user_email: str, conv_id: str) -> Dict[str, Any]:
        """获取或创建用户的智能体会话"""
        session_key = f"{user_email}_{conv_id}"
        if session_key not in self.agent_sessions:
            self.agent_sessions[session_key] = self._create_agent_session(user_email, conv_id)
        return self.agent_sessions[session_key]

    def get_response_stream(self, user_message: str, user_email: str, agent_type: str = "general", conv_id: Optional[str] = None, form_data: dict = None,collected_info: str = ""):
        """处理用户请求并返回响应流（支持Redis记忆）"""
        if not conv_id:
            raise ValueError("Conversation ID (conv_id) 不能为空")
            
        full_response = ""
        try:
            session = self.get_or_create_agent_session(user_email, conv_id)
            memory: RedisSimpleMemory = session['memory']
            
            # 获取对话历史记忆
            conversation_history = memory.messages

            if agent_type == "general":
                agent = session['normal_agent']
                answer = myanswer(user_message)
                if answer == '':
                    print(f"🔍 [SQL查询] 未找到相关信息，使用普通对话智能体处理。")
                    generator = agent.get_response_stream(user_message, conversation_history)
                else:
                    sql_message = user_message + f"本地查找到资料信息：{answer}"
                    print(f"🔍 [SQL查询] 找到相关信息，使用SQL智能体处理。")
                    generator = agent.get_response_stream(sql_message, conversation_history)
                # print(sql_message)
            
            elif agent_type == "travel":

                if is_travel_planning_request(user_message):
                    collector: InformationCollectorAgent = session["collector"]
                    planner  : PlannerAgent            = session["planner"]

                    # ① 先启动信息收集 —— 立即把结果 forward 给前端
                    info_text = ""
                    for event in collector.get_response_stream_with_frontend(user_message):
                        if isinstance(event, dict) and "info_collection_result" in event:
                            info_text = event["info_collection_result"]
                            full_response += info_text + "\n\n"          # 让它也写入 DB
                            yield event
                            continue                                     # <— 关键：跳过本轮，其它逻辑留给下一轮
                        yield event
                        
                    for txt in planner.get_response_stream(
                            user_message,
                            collected_info=info_text,
                            conversation_history=conversation_history):
                        full_response += txt
                        yield txt
                    return
                
                else:
                    agent = session['normal_agent']
                    generator = agent.get_response_stream(user_message, conversation_history)


            

            elif agent_type == "pdf_generator":
                agent = session['pdf_agent']
                generator = agent.get_response_stream(user_message, conversation_history)
            
            else:
                # Simple travel question with memory
                agent = session['normal_agent']
                generator = agent.get_response_stream(user_message, conversation_history)
            
            # 只有非旅行规划请求才需要从生成器消费内容
            if agent_type != "travel" or not is_travel_planning_request(user_message):
                # 从生成器消费内容并更新记忆
                for chunk in generator:
                    full_response += chunk
                    yield chunk
            
            # 保存对话到Redis记忆中
            memory.add_message("user", user_message)
            memory.add_message("assistant", full_response)
            print(f"💾 已保存对话到Redis记忆，当前记忆条数: {len(memory.messages)}")

        except Exception as e:
            error_msg = f"抱歉，处理您的请求时出现了问题: {str(e)}"
            print(f"处理请求时发生严重错误: {e}\n{traceback.format_exc()}")
            yield error_msg
            
            # 即使出错也保存到记忆中
            try:
                memory.add_message("user", user_message)
                memory.add_message("assistant", error_msg)
            except:
                pass
    
    def clear_user_sessions(self, user_email: str) -> int:
        """清除用户的所有会话记忆"""
        cleared_count = 0
        keys_to_delete = []
        
        # 找到所有需要清除的会话
        for session_key in list(self.agent_sessions.keys()):
            if session_key.startswith(user_email):
                keys_to_delete.append(session_key)
        
        # 清除内存中的会话
        for key in keys_to_delete:
            if key in self.agent_sessions:
                # 清除Redis记忆
                memory = self.agent_sessions[key]['memory']
                memory.clear()
                # 删除会话
                del self.agent_sessions[key]
                cleared_count += 1
        
        print(f"已清除用户 {user_email} 的 {cleared_count} 个会话记忆")
        return cleared_count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        stats = self.redis_memory_manager.get_memory_stats()
        stats["active_agent_sessions"] = len(self.agent_sessions)
        return stats

# =============================================================================
# 4. Main Service Instance and Compatibility Layer (The Public API)
# 懒加载全局实例：只在需要时才创建
# =============================================================================

_agent_service = None

def get_agent_service(redis_config=None) -> AgentService:
    """获取全局AgentService实例（懒加载）"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(redis_config=redis_config)
    return _agent_service

# --- 旧函数接口，现在代理到 AgentService ---
def get_agent_response_stream(user_message, user_email, agent_type="general", conv_id=None, form_data=None):
    """
    [兼容性接口] 获取智能体响应流。
    此函数现在是 AgentService.get_response_stream 的一个简单包装。
    """
    return get_agent_service().get_response_stream(user_message, user_email, agent_type, conv_id, form_data)

def load_mcp_tools_async():
    """[兼容性接口] 异步加载MCP工具"""
    return get_agent_service().mcp_manager.load_tools_async()

def load_mcp_tools_sync():
    """[兼容性接口] 同步加载MCP工具的包装器"""
    return get_agent_service().mcp_manager.load_tools_sync()

def clear_user_agent_sessions(user_email: str) -> int:
    """[新接口] 清除用户的所有智能体会话和Redis记忆"""
    return get_agent_service().clear_user_sessions(user_email)

def get_agent_memory_stats() -> Dict[str, Any]:
    """[新接口] 获取智能体记忆统计信息"""
    return get_agent_service().get_memory_stats()

def is_travel_planning_request(message: str) -> bool:
    """判断是否为旅行规划请求"""
    travel_keywords = ['旅行', '旅游', '出行', '行程', '规划', '计划', '机票', '酒店', '住宿', '景点', '路线',
                       'travel', 'trip', 'vacation', 'itinerary', 'plan', 'flight', 'hotel', 'attraction', 'route']
    return any(keyword in message.lower() for keyword in travel_keywords)
