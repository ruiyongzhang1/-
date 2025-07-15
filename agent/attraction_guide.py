from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain.memory.chat_message_histories import ChatMessageHistory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import Tool
import requests
import json
import time
from typing import List, Dict, Optional, Any
import asyncio
import aiohttp
from dataclasses import dataclass
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pydantic import SecretStr
import base64
import uuid

load_dotenv()

# ===== 数据模型 =====
@dataclass
class Attraction:
    name: str
    address: str
    latitude: float
    longitude: float
    category: str
    rating: float
    distance: float
    description: str = ""
    phone: str = ""
    opening_hours: str = ""
    ticket_price: str = ""

@dataclass
class GeneratedImage:
    """生成的图片信息"""
    url: str
    prompt: str
    timestamp: datetime
    seed: int = 0
    attraction_name: str = ""

# ===== API服务层 =====
class MapAPIService:
    """地图API服务类"""
    
    def __init__(self, gaode_key: str = ""):
        self.gaode_key = gaode_key or "d24e7f7d507304fda88b6bc4b1968c65"
        self.cache = {}
        self.cache_expiry = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    def _set_cache(self, key: str, data: Any, expiry_hours: int = 24):
        """设置缓存"""
        if not hasattr(self, 'cache'):
            self.cache = {}
        if not hasattr(self, 'cache_expiry'):
            self.cache_expiry = {}
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + timedelta(hours=expiry_hours)
    
    def get_nearby_attractions_gaode(self, location: str, radius: int = 5000) -> List[Attraction]:
        """使用高德地图API获取附近景点"""
        cache_key = f"gaode_{location}_{radius}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            # 1. 先获取地点坐标
            geocode_url = "https://restapi.amap.com/v3/geocode/geo"
            geocode_params = {
                "key": self.gaode_key,
                "address": location,
                "output": "json"
            }
            
            geo_response = requests.get(geocode_url, params=geocode_params, timeout=10)
            geo_data = geo_response.json()
            
            if geo_data["status"] != "1" or not geo_data["geocodes"]:
                return self._get_mock_attractions(location)
            
            coordinate = geo_data["geocodes"][0]["location"]
            
            # 2. 搜索附近景点
            search_url = "https://restapi.amap.com/v3/place/around"
            search_params = {
                "key": self.gaode_key,
                "location": coordinate,
                "keywords": "风景名胜|旅游景点|博物馆|公园|寺庙|古迹",
                "radius": radius,
                "output": "json",
                "extensions": "all"
            }
            
            search_response = requests.get(search_url, params=search_params, timeout=10)
            search_data = search_response.json()
            
            attractions = []
            if search_data["status"] == "1" and search_data["pois"]:
                for poi in search_data["pois"][:15]:
                    location_parts = poi.get("location", "0,0").split(",")
                    attraction = Attraction(
                        name=poi.get("name", ""),
                        address=poi.get("address", ""),
                        latitude=float(location_parts[1]) if len(location_parts) > 1 else 0,
                        longitude=float(location_parts[0]) if len(location_parts) > 0 else 0,
                        category=poi.get("type", "景点"),
                        rating=float(poi.get("biz_ext", {}).get("rating", "0") or "0"),
                        distance=float(poi.get("distance", "0")),
                        phone=poi.get("tel", ""),
                        description=poi.get("business_area", "")
                    )
                    attractions.append(attraction)
            
            self._set_cache(cache_key, attractions)
            return attractions
            
        except Exception as e:
            print(f"高德API调用失败: {e}")
            return self._get_mock_attractions(location)
    
    def _get_mock_attractions(self, location: str) -> List[Attraction]:
        """模拟景点数据（当API失败时使用）"""
        mock_data = {
            "北京": [
                Attraction("故宫博物院", "北京市东城区景山前街4号", 39.9163, 116.3903, "历史文化", 4.7, 1000),
                Attraction("天安门广场", "北京市东城区天安门广场", 39.9059, 116.3974, "历史文化", 4.6, 800),
                Attraction("颐和园", "北京市海淀区新建宫门路19号", 39.9999, 116.2755, "园林景观", 4.5, 2000),
                Attraction("八达岭长城", "北京市延庆区军都山关沟古道北口", 40.3577, 116.0154, "历史文化", 4.8, 60000),
                Attraction("天坛公园", "北京市东城区天坛内东里7号", 39.8732, 116.4119, "历史文化", 4.4, 1500)
            ],
            "杭州": [
                Attraction("西湖", "浙江省杭州市西湖区", 30.2477, 120.1503, "自然风光", 4.6, 500),
                Attraction("雷峰塔", "浙江省杭州市西湖区南山路15号", 30.2311, 120.1492, "历史文化", 4.3, 800),
                Attraction("灵隐寺", "浙江省杭州市西湖区法云弄1号", 30.2415, 120.1009, "宗教场所", 4.5, 1200),
                Attraction("千岛湖", "浙江省杭州市淳安县", 29.6054, 119.0423, "自然风光", 4.4, 80000),
                Attraction("宋城", "浙江省杭州市之江路148号", 30.1982, 120.1267, "主题公园", 4.2, 2000)
            ]
        }
        
        for city, attractions in mock_data.items():
            if city in location:
                return attractions
        
        # 默认返回一些通用景点
        return [
            Attraction("当地博物馆", f"{location}市中心", 0, 0, "历史文化", 4.0, 1000),
            Attraction("城市公园", f"{location}公园路", 0, 0, "自然风光", 4.2, 800),
            Attraction("古城墙", f"{location}老城区", 0, 0, "历史文化", 4.1, 1200)
        ]

class SearchAPIService:
    """搜索API服务类"""
    
    def __init__(self):
        # 简化版本，不使用外部搜索API，而是使用内置知识
        self.cache = {}
        self.cache_expiry = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    def _set_cache(self, key: str, data: str, expiry_hours: int = 6):
        """设置缓存"""
        if not hasattr(self, 'cache'):
            self.cache = {}
        if not hasattr(self, 'cache_expiry'):
            self.cache_expiry = {}
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + timedelta(hours=expiry_hours)
    
    def search_attraction_info(self, attraction_name: str, city: str = "") -> str:
        """获取景点详细信息（使用内置知识库）"""
        cache_key = f"search_{attraction_name}_{city}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        # 简化版：返回基本提示，让AI使用其内置知识
        info = f"请基于您的知识库为{attraction_name}提供详细介绍，包括历史背景、文化价值、建筑特色、参观建议等信息。"
        
        self._set_cache(cache_key, info)
        return info

# ===== 图片生成服务 =====
class ImageGenerationService:
    """硅基流动图片生成服务类"""
    
    def __init__(self):
        self.api_key = os.getenv("SILICONFLOW_API_KEY")
        self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = "Kwai-Kolors/Kolors"
        
        if not self.api_key:
            print("⚠️ 警告: 未配置硅基流动API密钥，图片生成功能将不可用")
        
        self.cache = {}
        self.cache_expiry = {}
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    def _set_cache(self, key: str, data: GeneratedImage, expiry_hours: int = 1):
        """设置缓存（图片URL有效期1小时）"""
        if not hasattr(self, 'cache'):
            self.cache = {}
        if not hasattr(self, 'cache_expiry'):
            self.cache_expiry = {}
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + timedelta(hours=expiry_hours)
    
    def _create_prompt_for_attraction(self, attraction_name: str, attraction_type: str = "", style: str = "realistic") -> str:
        """为景点创建图片生成提示词"""
        
        # 根据景点类型和名称生成合适的提示词
        base_prompts = {
            "历史文化": f"Ancient Chinese architecture of {attraction_name}, traditional buildings with elegant roofs, historical atmosphere, cultural heritage site, detailed architectural elements, warm lighting, high quality, photorealistic",
            "自然风光": f"Beautiful natural landscape of {attraction_name}, scenic mountain and water views, lush vegetation, peaceful atmosphere, golden hour lighting, high resolution, photorealistic",
            "宗教场所": f"Sacred temple or religious site {attraction_name}, traditional Chinese architecture, incense smoke, peaceful atmosphere, ancient trees, spiritual ambiance, soft lighting, detailed, photorealistic",
            "园林景观": f"Classical Chinese garden {attraction_name}, traditional pavilions, bridges over water, rock formations, beautiful plants, serene atmosphere, artistic composition, high quality",
            "博物馆": f"Modern museum building {attraction_name}, contemporary architecture, cultural exhibits, elegant interior design, professional lighting, educational atmosphere, high resolution",
            "主题公园": f"Exciting theme park {attraction_name}, colorful attractions, joyful atmosphere, entertainment facilities, vibrant colors, dynamic scene, high quality",
            "城市景观": f"Urban landmark {attraction_name}, modern cityscape, architectural beauty, bustling atmosphere, city lights, professional photography, high quality",
            "古镇村落": f"Ancient Chinese town or village {attraction_name}, traditional architecture, historical streets, cultural atmosphere, authentic details, warm lighting, photorealistic"
        }
        
        # 特殊景点的专门提示词
        special_prompts = {
            # 塔类景点
            "大雁塔": "Ancient Big Wild Goose Pagoda in Xi'an, traditional Chinese Buddhist architecture, tall brick pagoda, historical Buddhist temple, sunset lighting, detailed stonework, cultural heritage site, photorealistic",
            "小雁塔": "Small Wild Goose Pagoda in Xi'an, ancient Chinese pagoda, traditional Buddhist architecture, historical temple complex, serene atmosphere, detailed brickwork, photorealistic",
            "二七塔": "Erqi Tower in Zhengzhou, modern memorial tower, architectural landmark, urban setting, commemorative monument, city skyline, professional photography, high quality",
            "雷峰塔": "Leifeng Pagoda by West Lake, traditional Chinese pagoda, lakeside setting, beautiful landscape, historical architecture, scenic views, golden hour lighting, photorealistic",
            "六和塔": "Liuhe Pagoda in Hangzhou, ancient Chinese pagoda, traditional architecture, riverside location, historical monument, detailed craftsmanship, photorealistic",
            
            # 桥类景点
            "小商桥": "Ancient Xiaoshang Bridge in Luohe Henan, historical stone arch bridge, traditional Chinese bridge architecture, ancient engineering marvel, beautiful river scenery, cultural heritage site, photorealistic",
            "漯河小商桥": "Ancient Xiaoshang Bridge in Luohe Henan, historical stone arch bridge, traditional Chinese bridge architecture, ancient engineering marvel, beautiful river scenery, cultural heritage site, photorealistic",
            
            # 重庆景点
            "洪崖洞": "Hongya Cave in Chongqing, traditional Chinese stilt house architecture, night illumination, Jialing River waterfront, multilevel ancient-style buildings, colorful lighting, urban landscape, photorealistic",
            "重庆洪崖洞": "Hongya Cave in Chongqing, traditional Chinese stilt house architecture, night illumination, Jialing River waterfront, multilevel ancient-style buildings, colorful lighting, urban landscape, photorealistic",
            
            # 长城
            "长城": "Great Wall of China, ancient defensive fortification, winding through mountains, stone and brick construction, watchtowers, dramatic mountain landscape, historical monument, photorealistic",
            "北京长城": "Great Wall of China near Beijing, ancient defensive fortification, winding through mountains, stone and brick construction, watchtowers, dramatic mountain landscape, historical monument, photorealistic",
            "万里长城": "Great Wall of China, ancient defensive fortification, winding through mountains, stone and brick construction, watchtowers, dramatic mountain landscape, historical monument, photorealistic",
            "八达岭长城": "Badaling Great Wall, ancient Chinese fortification, restored section, mountain scenery, stone construction, tourists, clear blue sky, photorealistic",
            "慕田峪长城": "Mutianyu Great Wall, ancient Chinese fortification, well-preserved section, autumn foliage, mountain landscape, traditional architecture, photorealistic",
            
            # 宫殿类
            "故宫": "Forbidden City imperial palace, traditional Chinese royal architecture, red walls and golden roofs, grand courtyards, historical magnificence, detailed craftsmanship, photorealistic",
            "颐和园": "Summer Palace imperial garden, traditional Chinese architecture, beautiful lake views, classical pavilions, serene landscape, artistic composition, photorealistic",
            "华清宫": "Huaqing Palace in Xi'an, ancient imperial hot springs palace, traditional Chinese architecture, historical gardens, elegant buildings, warm lighting, photorealistic",
            
            # 兵马俑
            "兵马俑": "Terracotta Warriors in Xi'an, ancient Chinese clay soldiers, archaeological site, historical artifacts, underground museum, dramatic lighting, detailed sculpture, photorealistic",
            
            # 城墙类
            "西安城墙": "Ancient city wall of Xi'an, massive stone fortification, traditional Chinese defensive architecture, historical monument, sunset lighting, impressive scale, photorealistic",
            
            # 山峰类
            "华山": "Mount Hua steep cliffs and peaks, dramatic mountain landscape, natural stone formations, misty atmosphere, sunrise lighting, breathtaking views, photorealistic",
            "泰山": "Mount Tai sacred mountain, stone steps and ancient temples, natural landscape, cultural significance, morning mist, traditional architecture, photorealistic",
            
            # 特殊建筑
            "钟楼": "Ancient bell tower, traditional Chinese architecture, historical landmark, urban setting, detailed craftsmanship, warm evening lighting, photorealistic",
            "鼓楼": "Ancient drum tower, traditional Chinese architecture, historical monument, cultural significance, detailed woodwork, atmospheric lighting, photorealistic"
        }
        
        # 首先检查是否有特殊提示词
        for key, prompt in special_prompts.items():
            if key in attraction_name:
                return prompt
        
        # 根据景点类型选择合适的提示词
        for category, prompt in base_prompts.items():
            if category in attraction_type:
                return prompt
        
        # 基于景点名称中的关键词智能生成提示词
        if "洞" in attraction_name or "崖" in attraction_name:
            return f"Traditional Chinese architecture {attraction_name}, ancient cave dwellings or cliff buildings, unique architectural design, dramatic landscape setting, historical significance, detailed stonework, photorealistic"
        elif "桥" in attraction_name:
            return f"Ancient Chinese bridge {attraction_name}, traditional stone arch bridge architecture, historical engineering marvel, beautiful water scenery, cultural heritage site, detailed stonework, photorealistic"
        elif "塔" in attraction_name:
            return f"Ancient Chinese pagoda {attraction_name}, traditional tower architecture, historical Buddhist or cultural monument, detailed stonework or brickwork, serene atmosphere, photorealistic"
        elif "寺" in attraction_name or "庙" in attraction_name:
            return f"Traditional Chinese temple {attraction_name}, Buddhist or Taoist architecture, peaceful religious site, incense smoke, ancient trees, spiritual atmosphere, photorealistic"
        elif "宫" in attraction_name or "殿" in attraction_name:
            return f"Imperial Chinese palace {attraction_name}, traditional royal architecture, grand buildings, historical magnificence, detailed craftsmanship, golden lighting, photorealistic"
        elif "山" in attraction_name:
            return f"Majestic mountain {attraction_name}, natural landscape, dramatic peaks and valleys, misty atmosphere, scenic beauty, sunrise or sunset lighting, photorealistic"
        elif "湖" in attraction_name or "江" in attraction_name or "河" in attraction_name:
            return f"Beautiful water landscape {attraction_name}, serene lake or river views, natural scenery, peaceful atmosphere, reflection in water, golden hour lighting, photorealistic"
        elif "博物馆" in attraction_name:
            return f"Museum building {attraction_name}, modern or traditional architecture, cultural institution, elegant design, educational atmosphere, professional lighting, photorealistic"
        elif "古城" in attraction_name or "古镇" in attraction_name:
            return f"Ancient Chinese town {attraction_name}, traditional architecture, historical streets, cultural heritage, authentic atmosphere, warm lighting, photorealistic"
        elif "广场" in attraction_name:
            return f"Public square {attraction_name}, urban landmark, open space, architectural surroundings, city atmosphere, people gathering, professional photography"
        
        # 默认提示词 - 更通用和详细
        return f"Beautiful scenic view of {attraction_name}, Chinese tourist attraction, detailed architecture and landscape, cultural significance, professional photography, high quality, photorealistic, beautiful lighting"
    
    def generate_attraction_image(self, attraction: Attraction, style: str = "realistic", use_cache: bool = True) -> Optional[GeneratedImage]:
        """为景点生成图片"""
        
        if not self.api_key:
            print("❌ 图片生成失败: 未配置API密钥")
            return None
        
        # 检查缓存（如果启用缓存）
        cache_key = f"image_{attraction.name}_{style}"
        if use_cache and self._is_cache_valid(cache_key):
            print(f"✅ 使用缓存的图片: {attraction.name}")
            return self.cache[cache_key]
        
        try:
            print(f"🎨 正在为 {attraction.name} 生成图片...")
            
            # 创建提示词
            prompt = self._create_prompt_for_attraction(attraction.name, attraction.category, style)
            
            # 调用硅基流动API
            url = f"{self.base_url}/images/generations"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "prompt": prompt,
                "image_size": "1024x1024",
                "batch_size": 1,
                "num_inference_steps": 20,
                "guidance_scale": 7.5,
                "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text"
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("images") and len(result["images"]) > 0:
                    image_url = result["images"][0]["url"]
                    seed = result.get("seed", 0)
                    
                    generated_image = GeneratedImage(
                        url=image_url,
                        prompt=prompt,
                        timestamp=datetime.now(),
                        seed=seed,
                        attraction_name=attraction.name
                    )
                    
                    # 缓存结果（如果启用缓存）
                    if use_cache:
                        self._set_cache(cache_key, generated_image)
                    
                    print(f"✅ 图片生成成功: {attraction.name}")
                    return generated_image
                else:
                    print(f"❌ 图片生成失败: 响应中没有图片数据")
                    return None
            else:
                print(f"❌ 图片生成API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 图片生成异常: {str(e)}")
            return None
    
    def generate_custom_image(self, prompt: str, attraction_name: str = "") -> Optional[GeneratedImage]:
        """生成自定义提示词的图片"""
        
        if not self.api_key:
            print("❌ 图片生成失败: 未配置API密钥")
            return None
        
        try:
            print(f"🎨 正在生成自定义图片...")
            
            # 调用硅基流动API
            url = f"{self.base_url}/images/generations"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "prompt": prompt,
                "image_size": "1024x1024",
                "batch_size": 1,
                "num_inference_steps": 20,
                "guidance_scale": 7.5,
                "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text"
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("images") and len(result["images"]) > 0:
                    image_url = result["images"][0]["url"]
                    seed = result.get("seed", 0)
                    
                    generated_image = GeneratedImage(
                        url=image_url,
                        prompt=prompt,
                        timestamp=datetime.now(),
                        seed=seed,
                        attraction_name=attraction_name
                    )
                    
                    print(f"✅ 自定义图片生成成功")
                    return generated_image
                else:
                    print(f"❌ 图片生成失败: 响应中没有图片数据")
                    return None
            else:
                print(f"❌ 图片生成API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ 图片生成异常: {str(e)}")
            return None

# ===== 增强版导游智能体 =====
class EnhancedTourGuideAgent:
    def __init__(self, gaode_key: str = ""):
        load_dotenv()
        
        # 获取API配置 - 使用OpenAI API
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_API_URL")
        
        if not self.api_key:
            raise ValueError("未配置OpenAI API密钥")
        
        # 初始化大模型 - 使用OpenAI的gpt-4.1-nano模型
        self.llm = ChatOpenAI(
            temperature=0.7,
            api_key=SecretStr(self.api_key),
            model="gpt-4.1-nano",  # 使用gpt-4.1-nano模型
            base_url=self.base_url,
            streaming=True
        )
        
        # 初始化服务
        self.map_service = MapAPIService(gaode_key)
        self.search_service = SearchAPIService()
        self.image_service = ImageGenerationService()
        
        # 初始化记忆 - 使用新的ChatMessageHistory
        from langchain.memory.chat_message_histories import ChatMessageHistory
        from langchain.schema import BaseMessage
        
        self.message_history = ChatMessageHistory()
        self.current_style = "学术型"
        self.current_attractions = []
        self.enable_image_generation = True  # 控制是否启用图片生成
        self.chain = self._create_chain()
    
    def _create_chain(self):
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=self._get_enhanced_system_prompt()),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        return prompt | self.llm | StrOutputParser()
    
    def _get_enhanced_system_prompt(self) -> str:
        """增强版系统提示词"""
        style_prompts = {
            "学术型": "作为考古学专家，用严谨数据讲解，所有结论需标注来源",
            "故事型": "作为说书人，用生动叙事和感官描述（至少3个形容词）",
            "亲子型": "使用简单词汇和互动问题（语句<20字，带拟声词）",
            "网红风格": "加入emoji和拍照建议（推荐3个机位参数）",
            "幽默诙谐": "用轻松搞笑的方式讲解，穿插网络流行语和段子"
        }
        
        return f"""
        你是一名专业AI导游，当前使用【{self.current_style}】风格讲解。
        {style_prompts.get(self.current_style, "")}
        
        特别说明：
        1. 用户提供的景点信息来自真实的地图API数据
        2. 搜索信息来自最新的网络资源，请整合这些信息
        3. 如果搜索信息与你的知识有冲突，优先使用搜索到的最新信息
        4. 必须在回答中体现搜索到的实时信息（如门票价格、开放时间等）
        5. 始终使用Markdown格式回复
        
        必须遵守：
        1. 历史日期同时显示农历/公历
        2. 距离数据用公制/英制单位
        3. 宗教场所自动追加注意事项
        4. 餐饮信息标注人均消费区间
        5. 引用搜索信息时要自然融入，不要生硬标注"根据搜索"
        6. 每个小点单独成行，确保良好的可读性
        
        输出格式要求：
        
        # 🏛️ **景点名称**
        
        ## 📖 总体概况
        （1-2句话简要介绍）
        
        ## 📍 地理位置
        详细地址和位置信息
        
        ## ⏳ 历史时期
        建造时间和历史背景
        
        ## 🌟 核心亮点
        - 亮点1
        - 亮点2  
        - 亮点3
        - 亮点4
        - 亮点5
        
        ## 📜 深度讲解
        400-500字的详细历史背景、建筑特色和文化意义介绍
        
        ## 🎫 实用信息
        - **开放时间**：具体时间
        - **门票价格**：具体价格
        - **交通方式**：详细交通指南
        - **联系电话**：电话号码（如有）
        
        ## 💡 参观建议
        - 建议1
        - 建议2
        - 建议3
        
        ## ⚠️ 注意事项
        - 注意事项1
        - 注意事项2
        - 注意事项3
        """
    
    def set_style(self, style: str):
        """设置讲解风格"""
        valid_styles = ["学术型", "故事型", "亲子型", "网红风格", "幽默诙谐"]
        if style in valid_styles:
            self.current_style = style
            self.chain = self._create_chain()
            return f"已切换为【{style}】讲解风格"
        return "无效的风格选择"
    
    def get_nearby_attractions(self, location: str, radius: int = 5000) -> List[Attraction]:
        """获取附近景点"""
        print(f"🔍 正在搜索 {location} 附近 {radius/1000}km 范围内的景点...")
        attractions = self.map_service.get_nearby_attractions_gaode(location, radius)
        self.current_attractions = attractions
        return attractions
    
    def introduce_attraction_with_search(self, attraction: Attraction, city: str = "", generate_image: bool = True) -> tuple[str, Optional[GeneratedImage]]:
        """使用搜索增强的景点介绍，支持图片生成"""
        print(f"🔍 正在搜索 {attraction.name} 的最新信息...")
        
        # 搜索景点最新信息
        search_info = self.search_service.search_attraction_info(attraction.name, city)
        
        # 生成图片（如果启用）
        generated_image = None
        if generate_image and self.enable_image_generation:
            generated_image = self.image_service.generate_attraction_image(attraction)
        
        # 构建增强的查询
        query = f"""
        请用{self.current_style}风格详细介绍以下景点：
        
        【景点基本信息】（来自地图API）：
        - 名称：{attraction.name}
        - 地址：{attraction.address}
        - 坐标：{attraction.latitude}, {attraction.longitude}
        - 类型：{attraction.category}
        - 评分：{attraction.rating}/5.0
        - 距离：{attraction.distance}米
        - 电话：{attraction.phone or "暂无"}
        - 简介：{attraction.description or "暂无"}
        
        【最新搜索信息】：
        {search_info}
        
        请整合以上信息，生成专业的景点介绍。特别注意要自然融入搜索到的最新信息。
        """
        
        # 调用模型
        response = self.llm.invoke([
            SystemMessage(content=self._get_enhanced_system_prompt()),
            HumanMessage(content=query)
        ]).content
        
        # 如果生成了图片，在回答中添加图片信息
        if generated_image:
            # 直接使用原始图片URL
            image_section = self.create_image_section_with_fallback(
                generated_image.url, 
                attraction.name
            )
            response += image_section
            print(f"✅ 图片链接已成功嵌入到回答中: {attraction.name}")
            print(f"🔗 图片URL: {generated_image.url}")
        
        # 保存到记忆
        from langchain.schema import HumanMessage, AIMessage
        self.message_history.add_user_message(f"介绍{attraction.name}")
        self.message_history.add_ai_message(response)
        
        return response, generated_image
    
    def filter_attractions(self, attractions: List[Attraction], 
                          category: str = "", 
                          min_rating: float = 0,
                          max_distance: float = float('inf')) -> List[Attraction]:
        """筛选景点"""
        filtered = attractions
        
        if category:
            filtered = [a for a in filtered if category in a.category]
        
        if min_rating > 0:
            filtered = [a for a in filtered if a.rating >= min_rating]
        
        if max_distance < float('inf'):
            filtered = [a for a in filtered if a.distance <= max_distance]
        
        # 按评分和距离排序
        filtered.sort(key=lambda x: (-x.rating, x.distance))
        
        return filtered

    def stream_attraction_guide(self, user_input: str, generate_image: bool = True):
        """流式返回景点讲解内容，支持图片生成"""
        try:
            # 检查用户是否询问特定景点，如果没有预设景点，则根据用户输入创建临时景点对象
            attraction_to_generate = None
            if self.current_attractions:
                # 从已搜索的景点中查找匹配
                for attraction in self.current_attractions:
                    if attraction.name in user_input:
                        attraction_to_generate = attraction
                        break
            
            # 如果没有找到预设景点，但用户明确询问某个景点，则创建临时景点对象用于图片生成
            if not attraction_to_generate and generate_image and self.enable_image_generation:
                # 智能景点名称提取逻辑
                import re
                
                # 扩展的景点关键词模式 - 更全面的匹配
                attraction_patterns = [
                    # 北京景点
                    r'故宫博物院|故宫',
                    r'天安门广场|天安门',
                    r'长城|八达岭长城|万里长城|居庸关长城|慕田峪长城|北京长城',
                    r'颐和园',
                    r'天坛公园|天坛',
                    r'北海公园|北海',
                    r'景山公园|景山',
                    r'圆明园',
                    r'明十三陵|十三陵',
                    r'恭王府',
                    r'雍和宫',
                    r'鸟巢|国家体育场',
                    r'水立方|国家游泳中心',
                    
                    # 重庆景点
                    r'洪崖洞|重庆洪崖洞',
                    r'解放碑|重庆解放碑',
                    r'磁器口|磁器口古镇',
                    r'朝天门|重庆朝天门',
                    r'武隆天坑|武隆',
                    r'大足石刻',
                    r'红岩村|红岩革命纪念馆',
                    
                    # 西安景点
                    r'大雁塔|大慈恩寺',
                    r'小雁塔|荐福寺',
                    r'兵马俑|秦始皇兵马俑|秦兵马俑',
                    r'华清宫|华清池',
                    r'西安城墙|明城墙',
                    r'钟楼|西安钟楼',
                    r'鼓楼|西安鼓楼',
                    r'大明宫|大明宫遗址',
                    r'陕西历史博物馆',
                    r'回民街|回坊',
                    
                    # 郑州景点
                    r'二七塔|二七纪念塔',
                    r'河南博物院',
                    r'黄河风景名胜区',
                    r'郑州城隍庙',
                    r'嵩山|少林寺',
                    r'中原福塔',
                    
                    # 河南其他景点
                    r'小商桥|漯河小商桥',
                    r'开封府|开封',
                    r'龙门石窟',
                    r'白马寺',
                    r'云台山',
                    r'红旗渠',
                    
                    # 杭州景点
                    r'西湖',
                    r'雷峰塔',
                    r'灵隐寺',
                    r'千岛湖',
                    r'宋城',
                    r'西溪湿地',
                    r'六和塔',
                    r'苏堤|白堤',
                    
                    # 五岳名山
                    r'黄山',
                    r'泰山',
                    r'华山',
                    r'峨眉山',
                    r'衡山',
                    r'恒山',
                    r'嵩山',
                    
                    # 其他著名景点
                    r'九寨沟',
                    r'张家界',
                    r'桂林山水',
                    r'漓江',
                    r'天门山',
                    r'黄果树瀑布',
                    r'三峡|长江三峡',
                    r'武当山',
                    r'庐山',
                    r'普陀山',
                    r'五台山',
                    r'天坛',
                    r'乐山大佛',
                    r'都江堰'
                ]
                
                # 通用景点后缀模式 - 用于识别没有预定义的景点
                generic_patterns = [
                    r'([^，。！？\s]{2,10}(?:洞|崖|桥|塔|寺|庙|宫|殿|观|亭|楼|阁|园|湖|江|河|海|山|峰|峡|瀑布|古城|遗址|博物馆|纪念馆|公园|广场|大桥|古镇|村落|景区|风景区))',
                    r'([^，。！？\s]{2,10}(?:故居|陵墓|墓|祠堂|书院|学府|大学|府邸|王府|府第))',
                    r'([^，。！？\s]{2,10}(?:古街|老街|步行街|商业街|文化街|美食街))',
                    r'([^，。！？\s]{2,10}(?:古村|古镇|水乡|古城|老城|新城|开发区))'
                ]
                
                # 首先尝试精确匹配预定义景点
                attraction_name = None
                for pattern in attraction_patterns:
                    match = re.search(pattern, user_input)
                    if match:
                        attraction_name = match.group()
                        break
                
                # 如果没有精确匹配，尝试通用模式匹配
                if not attraction_name:
                    for pattern in generic_patterns:
                        matches = re.findall(pattern, user_input)
                        if matches:
                            # 选择最长的匹配作为景点名称
                            attraction_name = max(matches, key=len)
                            break
                
                # 如果仍然没有匹配，尝试提取包含地名的景点
                if not attraction_name:
                    # 地名+景点类型的模式 - 改进版
                    city_attraction_patterns = [
                        r'([^，。！？\s]*?[市县区镇]?)\s*([^，。！？\s]{2,8}(?:洞|崖|桥|塔|寺|庙|宫|殿|观|亭|楼|阁|园|湖|山|峰|景区|古城|博物馆|公园|广场))',
                        r'(重庆|北京|上海|天津|河南|漯河|开封|洛阳|郑州|安阳|新乡|焦作|濮阳|许昌|漯河|三门峡|南阳|商丘|信阳|周口|驻马店|济源|西安|杭州|苏州|南京)\s*([^，。！？\s]{2,8}(?:洞|崖|桥|塔|寺|庙|宫|殿|观|亭|楼|阁|园|湖|山|峰|景区|古城|博物馆|公园|广场))'
                    ]
                    
                    for pattern in city_attraction_patterns:
                        match = re.search(pattern, user_input)
                        if match:
                            city, attraction = match.groups()
                            # 如果景点名称已经包含地名，就直接使用，否则组合
                            if city and city.strip() and not attraction.startswith(city.strip()):
                                attraction_name = f"{city.strip()}{attraction}"
                            else:
                                attraction_name = attraction
                            break
                
                if attraction_name:
                    # 智能推断景点类型
                    def infer_category(name):
                        if any(keyword in name for keyword in ['桥', '塔', '寺', '庙', '宫', '殿', '观', '祠', '陵', '墓', '故居', '遗址']):
                            return '历史文化'
                        elif any(keyword in name for keyword in ['山', '峰', '峡', '湖', '海', '江', '河', '瀑布', '森林', '湿地']):
                            return '自然风光'
                        elif any(keyword in name for keyword in ['园', '公园', '花园', '植物园', '动物园']):
                            return '园林景观'
                        elif any(keyword in name for keyword in ['博物馆', '纪念馆', '展览馆', '美术馆', '科技馆']):
                            return '博物馆'
                        elif any(keyword in name for keyword in ['广场', '街', '商业区', '步行街']):
                            return '城市景观'
                        elif any(keyword in name for keyword in ['古镇', '古村', '水乡', '古城']):
                            return '古镇村落'
                        else:
                            return '历史文化'  # 默认类型
                    
                    category = infer_category(attraction_name)
                    
                    # 创建临时景点对象
                    attraction_to_generate = Attraction(
                        name=attraction_name,
                        address=f"{attraction_name}景区",
                        latitude=0.0,
                        longitude=0.0,
                        category=category,
                        rating=4.5,
                        distance=0,
                        description=f"著名景点{attraction_name}"
                    )
                    print(f"🎯 智能识别到景点: {attraction_name} (类型: {category})")
                else:
                    print("❌ 未能识别到有效的景点名称")
            
            # 增强用户输入，添加更多上下文
            enhanced_input = f"""
            作为专业的景点讲解员，请用{self.current_style}风格详细介绍用户询问的景点。
            
            用户请求：{user_input}
            
            请严格按照Markdown格式要求回答，确保：
            1. 使用清晰的标题层级（# ## ###）
            2. 列表项目单独成行，使用 - 开头
            3. 重要信息使用 **粗体** 标记
            4. 每个部分之间有适当的空行分隔
            5. 确保内容详实、准确、格式规范
            
            请严格按照系统提示中的输出格式要求来组织内容。
            """
            
            # 调用AI模型
            response = self.chain.invoke({
                "input": enhanced_input,
                "history": self.message_history.messages
            })
            
            # 清理AI回答中可能包含的图片相关内容，避免重复显示
            import re
            # 移除AI回答中的图片展示部分（如果有的话）
            response = re.sub(r'## 🖼️.*?</div>\s*```', '', response, flags=re.DOTALL)
            response = re.sub(r'📷.*?网络可能受限.*?\n', '', response, flags=re.DOTALL)
            response = re.sub(r'\*.*?景观图\*\s*\n', '', response, flags=re.DOTALL)
            
            # 如果找到了相关景点且启用图片生成，则生成图片
            generated_image = None
            if attraction_to_generate and generate_image and self.enable_image_generation:
                print(f"🎨 正在为 {attraction_to_generate.name} 生成图片...")
                generated_image = self.image_service.generate_attraction_image(attraction_to_generate, use_cache=True)
                
                if generated_image:
                    # 直接使用原始图片URL
                    image_section = self.create_image_section_with_fallback(
                        generated_image.url, 
                        attraction_to_generate.name
                    )
                    response += image_section
                    print(f"✅ 图片链接已成功嵌入到回答中: {attraction_to_generate.name}")
                    print(f"🔗 图片URL: {generated_image.url}")
                else:
                    print(f"❌ 图片生成失败: {attraction_to_generate.name}")
            
            # 保存到记忆
            from langchain.schema import HumanMessage, AIMessage
            self.message_history.add_user_message(user_input)
            self.message_history.add_ai_message(response)
            
            # 优化流式输出，按句子分割而不是单词
            sentences = response.replace('\n\n', '\n').split('\n')
            for sentence in sentences:
                if sentence.strip():
                    yield sentence + '\n'
                    time.sleep(0.03)  # 减少延迟，提升体验
                else:
                    yield '\n'
                    time.sleep(0.01)
                
        except Exception as e:
            error_message = f"抱歉，在处理您的请求时出现了错误：{str(e)}"
            print(f"景点讲解错误: {e}")
            yield error_message
    
    def toggle_image_generation(self, enabled: bool) -> str:
        """开启或关闭图片生成功能"""
        self.enable_image_generation = enabled
        status = "已开启" if enabled else "已关闭"
        return f"图片生成功能{status}"
    
    def generate_custom_attraction_image(self, prompt: str, attraction_name: str = "") -> Optional[GeneratedImage]:
        """生成自定义景点图片"""
        if not self.enable_image_generation:
            print("❌ 图片生成功能已关闭")
            return None
        
        return self.image_service.generate_custom_image(prompt, attraction_name)
    
    def create_image_section_with_fallback(self, image_url: str, attraction_name: str) -> str:
        """创建图片展示部分 - 简化版"""
        # 使用外部服务生成SVG占位图片
        from image_proxy import image_proxy_service
        fallback_image = image_proxy_service.generate_placeholder_svg_base64(attraction_name)
        
        # 生成唯一的图片ID，避免重复加载问题
        import uuid
        image_id = f"img_{uuid.uuid4().hex[:8]}"
        
        # 直接使用原始URL显示图片，同时提供SVG占位图片作为备用
        return f"""

## 🖼️ 景点视觉展示

<div class="image-container" style="text-align: center; margin: 20px 0;">
    <img id="{image_id}" src="{image_url}" 
         alt="{attraction_name}" 
         style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin: 10px 0;" 
         onerror="if(this.src !== '{fallback_image}') {{ this.src='{fallback_image}'; console.log('图片加载失败，已切换到占位图'); }}" />
    <p style="margin-top: 10px; font-style: italic; color: #666; font-size: 14px;">
        *AI生成的{attraction_name}景观图*
    </p>
    <div style="margin-top: 8px;">
        <a href="{image_url}" target="_blank" class="image-link" style="color: #007bff; text-decoration: none; font-size: 12px; padding: 4px 8px; background-color: #e3f2fd; border-radius: 4px;">
            🔗 查看原始图片
        </a>
    </div>
</div>
"""

# 全局变量存储用户的导游智能体实例
user_tour_guide_agents = {}

def get_tour_guide_agent(email: str) -> EnhancedTourGuideAgent:
    """获取或创建用户的导游智能体实例"""
    if email not in user_tour_guide_agents:
        user_tour_guide_agents[email] = EnhancedTourGuideAgent()
    return user_tour_guide_agents[email]

def clear_tour_guide_agents(email: str):
    """清除用户的导游智能体实例"""
    if email in user_tour_guide_agents:
        del user_tour_guide_agents[email]

def get_attraction_guide_response_stream(user_message: str, email: str, generate_image: bool = True):
    """获取景点讲解的流式响应，支持图片生成"""
    agent = get_tour_guide_agent(email)
    return agent.stream_attraction_guide(user_message, generate_image)

def toggle_image_generation_for_user(email: str, enabled: bool) -> str:
    """为特定用户开启或关闭图片生成功能"""
    agent = get_tour_guide_agent(email)
    return agent.toggle_image_generation(enabled)

def generate_attraction_image_for_user(email: str, attraction_name: str, custom_prompt: str = "") -> Optional[GeneratedImage]:
    """为用户生成景点图片"""
    agent = get_tour_guide_agent(email)
    
    if custom_prompt:
        return agent.generate_custom_attraction_image(custom_prompt, attraction_name)
    else:
        # 查找景点信息
        for attraction in agent.current_attractions:
            if attraction.name == attraction_name:
                return agent.image_service.generate_attraction_image(attraction)
        return None