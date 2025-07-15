import warnings
import os
import asyncio
import time
import traceback
import concurrent.futures
from typing import Dict, Any, List, Optional, Generator
from agent.RAG.retriever import rag_search
from agent.sql.attraction_ezqa_service import myanswer

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
    
    def create_llm(self, model: str = "gpt-4.1-nano", temperature: float = 0.1, 
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
    
    async def load_tools_async(self) -> List[Any]:
        """异步加载MCP工具"""
        try:
            # 直接导入本地MCP工具，避免MCP协议加载问题
            from agent.mcp_server import get_current_time, search_google, search_google_maps, search_google_flights, search_google_hotels
            from langchain.tools import tool
            
            # 创建LangChain工具包装器
            tools = []
            
            # 包装get_current_time
            @tool
            async def get_current_time_tool(format: str = "iso") -> str:
                """获取当前系统时间和旅行日期建议"""
                result = await get_current_time(format=format)
                if isinstance(result, dict) and "date" in result:
                    return f"当前时间: {result['date']}"
                else:
                    return str(result)
            
            # 包装search_google
            @tool
            async def search_google_tool(q: str) -> str:
                """搜索Google搜索结果"""
                result = await search_google(q=q)
                if isinstance(result, dict):
                    if "error" in result:
                        return f"搜索失败: {result['error']}"
                    elif "organic_results" in result:
                        results = result["organic_results"][:5]  # 取前5个结果
                        search_summary = []
                        for r in results:
                            title = r.get('title', '')
                            snippet = r.get('snippet', '')[:100]  # 截取前100字符
                            search_summary.append(f"{title}: {snippet}")
                        return f"找到 {len(results)} 个搜索结果:\n" + "\n".join(search_summary)
                    else:
                        return f"搜索完成，结果: {list(result.keys())}"
                else:
                    return str(result)
            
            # 包装search_google_maps
            @tool
            async def search_google_maps_tool(query: str) -> str:
                """搜索Google地图上的地点或服务"""
                result = await search_google_maps(query=query)
                if isinstance(result, dict):
                    if "error" in result:
                        return f"地图搜索失败: {result['error']}"
                    elif "local_results" in result:
                        results = result["local_results"][:5]  # 取前5个结果
                        map_summary = []
                        for r in results:
                            title = r.get('title', '')
                            address = r.get('address', '')
                            rating = r.get('rating', '')
                            map_summary.append(f"{title} - {address} - 评分:{rating}")
                        return f"找到 {len(results)} 个地点:\n" + "\n".join(map_summary)
                    else:
                        return f"地图搜索完成，结果: {list(result.keys())}"
                else:
                    return str(result)
            
            # 包装search_google_flights
            @tool
            async def search_google_flights_tool(departure_id: str, arrival_id: str, outbound_date: str, flight_type: str = "round_trip", return_date: str = None) -> str:
                """搜索Google航班信息"""
                # 自动处理日期，如果没有提供或日期不合理
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
                    return_date=return_date
                )
                if isinstance(result, dict):
                    if "error" in result:
                        return f"航班搜索失败: {result['error']}"
                    elif "flights" in result:
                        flights = result["flights"][:5]  # 取前5个航班
                        flight_summary = []
                        for flight in flights:
                            airline = flight.get('airline', '')
                            departure_time = flight.get('departure_time', '')
                            arrival_time = flight.get('arrival_time', '')
                            price = flight.get('price', '')
                            flight_summary.append(f"{airline} - {departure_time}到{arrival_time} - {price}")
                        return f"找到 {len(flights)} 个航班:\n" + "\n".join(flight_summary)
                    else:
                        return f"航班搜索完成，结果: {list(result.keys())}"
                else:
                    return str(result)
            
            # 包装search_google_hotels
            @tool
            async def search_google_hotels_tool(q: str, check_in_date: str = None, check_out_date: str = None) -> str:
                """搜索Google酒店信息"""
                # 如果没有提供日期，自动使用合理的未来日期
                from datetime import datetime, timedelta
                today = datetime.now()
                
                if not check_in_date:
                    check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                if not check_out_date:
                    check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                
                # 验证日期是否合理（不能是过去日期）
                try:
                    check_in = datetime.strptime(check_in_date, "%Y-%m-%d")
                    if check_in.date() < today.date():
                        # 如果入住日期是过去，调整为明天
                        check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                        check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                except ValueError:
                    # 如果日期格式错误，使用默认日期
                    check_in_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
                    check_out_date = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                
                result = await search_google_hotels(
                    q=q,
                    check_in_date=check_in_date,
                    check_out_date=check_out_date
                )
                if isinstance(result, dict):
                    if "error" in result:
                        return f"酒店搜索失败: {result['error']}"
                    elif "properties" in result:
                        properties = result["properties"][:5]  # 取前5个酒店
                        hotel_list = []
                        for prop in properties:
                            title = prop.get('title', '未知酒店')
                            price = prop.get('price', '价格未知')
                            rating = prop.get('rating', '评分未知')
                            hotel_list.append(f"{title} - {price} - 评分:{rating}")
                        return f"找到 {len(properties)} 个酒店: {'; '.join(hotel_list)}"
                    else:
                        return f"酒店搜索完成，结果: {list(result.keys())}"
                else:
                    return str(result)
            
            tools = [
                get_current_time_tool,
                search_google_tool,
                search_google_maps_tool,
                search_google_flights_tool,
                search_google_hotels_tool
            ]
            
            print(f"异步加载了 {len(tools)} 个本地MCP工具")
            return tools
            
        except Exception as e:
            print(f"异步加载MCP工具失败: {e}")
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
    def run_async_in_thread(async_func_or_coro, timeout: int = 60):
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
            return future.result(timeout=timeout)

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
            # print(f"📊 [MCP调试] 响应内容预览: {response_content[:200]}...")
            
            return response_content
            
        except Exception as e:
            print(f"❌ [MCP调试] 信息收集过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return f"信息收集失败: {str(e)}"
    
    def get_response_stream(self, message: str):
        """获取响应流"""
        try:
            full_response = AsyncSyncWrapper.run_async_in_thread(
                lambda: self.collect_information_async(message)
            )
            yield from StreamingUtils.stream_text(full_response)
        except Exception as e:
            yield f"处理请求时出现错误: {str(e)}"

class PlannerAgent:
    """行程规划智能体"""
    def __init__(self, llm_streaming: ChatOpenAI, llm_normal: ChatOpenAI):
        self.llm_streaming = llm_streaming
        self.llm_normal = llm_normal
        print("行程规划智能体已创建")
        
    def get_response_stream(self, message: str, collected_info: str = "", conversation_history: list = None):
        """获取真流式响应（支持对话记忆）"""
        # 构建规划请求内容
        if collected_info:
            planning_content = f"用户原始需求：\n{message}\n\n信息收集智能体提供的详细信息：\n{collected_info}"
        else:
            planning_content = f"用户需求：\n{message}"
        planning_content = planning_content + rag_search(message, top_k=3)['context']  # 添加RAG搜索结果
        
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

    def get_or_create_agent_session(self, user_email: str, conv_id: str) -> Dict[str, Any]:
        """获取或创建用户的智能体会话"""
        session_key = f"{user_email}_{conv_id}"
        if session_key not in self.agent_sessions:
            self.agent_sessions[session_key] = self._create_agent_session(user_email, conv_id)
        return self.agent_sessions[session_key]

    def get_response_stream(self, user_message: str, user_email: str, agent_type: str = "general", conv_id: Optional[str] = None):
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
                    # Multi-agent workflow with memory
                    collector_agent = session['collector']
                    planner_agent = session['planner']

                    '''
                    print(f"\n🎯 [旅行规划] 检测到旅行规划请求: {user_message}")
                    print(f"🔧 [旅行规划] 信息收集智能体工具数量: {len(collector_agent.tools)}")
                    print(f"📅 [旅行规划] 开始信息收集阶段...")
                    
                    print("旅行规划流程: [1] 信息收集中...")
                    '''

                    # 直接使用同步方式调用信息收集
                    collected_info = collector_agent.get_response_stream(user_message)
                    # 收集完整响应
                    collected_info_text = ""
                    for chunk in collected_info:
                        collected_info_text += chunk
                    
                    print(f"📊 [旅行规划] 信息收集完成，收集到的信息长度: {len(collected_info_text)} 字符")
                    # print(f"📋 [旅行规划] 收集到的信息预览: {collected_info_text[:300]}...")
                    print("旅行规划流程: [2] 开始流式行程规划...")
                    generator = planner_agent.get_response_stream(user_message, collected_info, conversation_history)
                else:
                    # Simple travel question with memory
                    agent = session['normal_agent']
                    generator = agent.get_response_stream(user_message, conversation_history)

            elif agent_type == "pdf_generator":
                agent = session['pdf_agent']
                generator = agent.get_response_stream(user_message, conversation_history)
            
            else:
                raise ValueError(f"未知的智能体类型: {agent_type}")

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
def get_agent_response_stream(user_message, user_email, agent_type="general", conv_id=None):
    """
    [兼容性接口] 获取智能体响应流。
    此函数现在是 AgentService.get_response_stream 的一个简单包装。
    """
    return get_agent_service().get_response_stream(user_message, user_email, agent_type, conv_id)

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
