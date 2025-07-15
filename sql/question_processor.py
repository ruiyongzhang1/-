import logging
import jieba
import re
from dotenv import load_dotenv
from openai import OpenAI
import os
import openai

jieba.setLogLevel(logging.ERROR)

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE')

class QuestionProcessor:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.city_dict = set()  # 城市词典
        self.short_to_full = {}  # 简称到全称的映射
        self.spot_dict = set()  # 景点词典
        self._load_city_dict()
        self._load_spot_dict()
        
        # 问题类型映射
        self.question_types = {
            "city_spots": ["有哪些景点", "有什么景点", "推荐景点", "景点有哪些", "旅游景点"],
            "compound_filter": ["和", "且", "同时", "既", "又", "还"],
            "ticket_price": ["价格", "门票", "多少钱", "费用"],
            "rating_spots": ["评分", "高", "最好", "推荐", "口碑"],
            "spot_info": ["位置", "地址", "电话", "开放时间", "营业时间", "所在城市", "门票价格", "评分", "介绍", "信息"],
            "nearby_spots": ["附近"]  # 新增附近景点推荐问题类型
        }

    def _load_city_dict(self):
        """加载城市词典，确保与数据库格式一致"""
        try:
            cities = self.db_manager.get_all_cities()
            self.city_dict = set(cities)
            
            # 创建简称到全称的映射（如 "北京" -> "北京市"）
            for city in self.city_dict:
                if city.endswith("市"):
                    short_name = city.rstrip("市")
                    self.short_to_full[short_name] = city
        except Exception:
            # 备选方案
            self.city_dict = {"北京市", "上海市", "广州市"}
            self.short_to_full = {"北京": "北京市", "上海": "上海市", "广州": "广州市"}

    def _load_spot_dict(self):
        """加载景点词典"""
        try:
            spots = self.db_manager.get_all_spots()
            self.spot_dict = set(spots)
        except Exception:
            # 备选方案
            self.spot_dict = {"法海寺", "红螺寺", "明十三陵", "颐和园", "故宫博物院", "天坛公园"}

    def _extract_city_name(self, question):
        """提取城市名称并转换为数据库存储的格式"""
        # 1. 尝试完整匹配
        for city in self.city_dict:
            if city in question:
                return city
        
        # 2. 尝试匹配简称并转换为全称
        for short_name, full_name in self.short_to_full.items():
            if short_name in question:
                return full_name
        
        # 3. 使用jieba分词辅助
        words = jieba.cut(question)
        for word in words:
            if word in self.city_dict:
                return word
            elif word in self.short_to_full:
                full_name = self.short_to_full[word]
                return full_name
        
        return None

    def _extract_spot_name(self, question):
        """提取景点名称"""
        # 1. 尝试完整匹配
        for spot in self.spot_dict:
            if spot in question:
                return spot
        
        # 2. 使用jieba分词辅助
        words = jieba.cut(question)
        for word in words:
            if word in self.spot_dict:
                return word
        
        return None

    def _extract_spot_attributes(self, question):
        """提取用户想要查询的景点属性"""
        attributes = []
        for attr_keyword, keywords in self.question_types.items():
            if attr_keyword == "spot_info":
                for keyword in keywords:
                    if keyword in question:
                        attributes.append(keyword)
        return attributes

    def _extract_price(self, question):
        """从问题中提取价格信息及比较条件"""
        try:
            # 提取价格数字
            price_match = re.search(r'(\d+(?:\.\d+)?)', question)
            if not price_match:
                return None
                
            price = float(price_match.group(1))
            
            # 提取比较条件
            if "低于" in question or "小于" in question or "不超过" in question:
                return {"value": price, "operator": "<="}
            elif "高于" in question or "大于" in question:
                return {"value": price, "operator": ">"}
            elif "不低于" in question or "不小于" in question:
                return {"value": price, "operator": ">="}
            else:
                # 默认使用小于等于
                return {"value": price, "operator": "<="}
        except Exception:
            return None

    def _extract_rating(self, question):
        """从问题中提取评分信息及比较条件"""
        try:
            # 处理"高"、"最好"等模糊表述
            if "高" in question or "最好" in question or "最高" in question:
                return {"value": 4.5, "operator": ">="}
                
            # 提取具体评分数字
            rating_match = re.search(r'(\d+(?:\.\d+)?)', question)
            if not rating_match:
                return None
                
            rating = float(rating_match.group(1))
            
            # 检查评分范围有效性
            if rating < 0 or rating > 5:
                return None
                
            # 提取比较条件
            if "不低于" in question or "不小于" in question or "至少" in question:
                return {"value": rating, "operator": ">="}
            
            elif "低于" in question or "小于" in question:
                return {"value": rating, "operator": "<"}
            
            elif "高于" in question or "大于" in question:
                return {"value": rating, "operator": ">"}
            
            else:
                # 默认使用大于等于
                return {"value": rating, "operator": ">="}
        except Exception:
            return None    

    def _use_llm_for_normalization(self, question):
        """使用大模型对用户问题进行规范化处理"""

        client = OpenAI(
            base_url=OPENAI_API_BASE,
            api_key=OPENAI_API_KEY,
        )

        if not OPENAI_API_KEY:
            return question
            
        try:
            # 构建提示词，引导模型进行规范化
            prompt = f"""
            你是一个智能旅游助手，擅长理解用户关于旅游景点的问题。
            请对以下问题进行规范化处理，包括将景点名称简写转换为全称，确保城市名称使用全称：
            对于问题中的如下关键词，无需改动：位置，评分，联系方式，时间，价格，门票，开放时间，电话，地址，网址，评分。

            原始问题: "{question}"
            
            规范化后的问题: 
            """
            
            response = client.chat.completions.create(
                    messages=[
                    {"role": "system", "content": "你是一个智能旅游助手，擅长规范化用户关于旅游景点的问题。"},
                    {"role": "user", "content": prompt}
                ],
                    model="gpt-4.1-nano",  # 使用常用模型
                )

            
            normalized_question = response.choices[0].message.content.strip()
            return normalized_question
        except Exception:
            return question

    def process(self, user_question):
        """处理用户问题，识别问题类型"""
        user_question = user_question.strip().lower()
        
        # 首次尝试解析问题
        processed_questions = self._try_process_question(user_question)
        
        # 如果解析结果为unknown，尝试使用大模型进行规范化
        if len(processed_questions) == 1 and processed_questions[0]["type"] == "unknown":
            normalized_question = self._use_llm_for_normalization(user_question)
            
            if normalized_question != user_question:
                processed_questions = self._try_process_question(normalized_question)
                for q in processed_questions:
                    q["original_question"] = user_question
                    q["normalized_question"] = normalized_question
        
        return processed_questions

    def _try_process_question(self, question):
        """尝试处理问题，返回处理结果"""
        # 先尝试提取景点名称
        spot_name = self._extract_spot_name(question)
        
        if spot_name:
            # 判断是否存在附近等关键词
            has_nearby_keyword = any(keyword in question for keyword in self.question_types["nearby_spots"])
            if has_nearby_keyword:
                return [{"type": "nearby_spots", "spot_name": spot_name, "message": question}]
            else:
                attributes = self._extract_spot_attributes(question)
                if attributes:
                    return [{"type": "spot_info", "spot_name": spot_name, "attributes": attributes, "message": question}]
                else:
                    # 如果没有指定属性，默认查询所有信息
                    return [{"type": "spot_info", "spot_name": spot_name, "attributes": ["位置", "电话", "营业时间", "评分", "门票价格", "所在城市"], "message": question}]
        
        # 若不包含景点名称，尝试提取城市名称
        city_name = self._extract_city_name(question)
        
        if city_name:
            # 检查是否为简单城市景点查询
            is_simple_query = any(keyword in question for keyword in self.question_types["city_spots"])
            
            # 提取其他条件
            has_price_condition = any(keyword in question for keyword in self.question_types["ticket_price"])
            has_rating_condition = any(keyword in question for keyword in self.question_types["rating_spots"])
            
            # 判断是否为复合查询
            is_compound_query = False
            keywords = []
            
            if has_price_condition or has_rating_condition:
                is_compound_query = True
                keywords.append({"type": "city_spots", "city_name": city_name})
                
                if has_price_condition:
                    price_info = self._extract_price(question)
                    if price_info:
                        keywords.append({"type": "ticket_price", "price": price_info})
                
                if has_rating_condition:
                    rating_info = self._extract_rating(question)
                    if rating_info:
                        keywords.append({"type": "rating_spots", "rating": rating_info})
            
            if is_compound_query and keywords:
                return [{"type": "compound_filter", "keywords": keywords, "message": question}]
            
            if is_simple_query and not is_compound_query:
                return [{"type": "city_spots", "city_name": city_name, "message": question}]
            
            return [{"type": "unknown", "message": f"无法识别的城市相关查询: {question}"}]
        
        return [{"type": "unknown", "message": "无法解答"}]    