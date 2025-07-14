import re
import logging
import functools

try:
    import jieba
except ImportError:
    logging.warning("未安装jieba库，分词功能将受限")


class QuestionProcessor:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.spot_dict = self._load_spot_dict()
        
        # 定义问题类型和关键词映射
        self.question_types = {
            "nearby": ["附近", "周边", "周围", "边上", "近"],
            "open_time": ["营业时间", "开放时间", "几点开门", "几点关门", "关门时间", "开门时间"],
            "ticket_price": ["门票", "票价", "多少钱", "价格", "费用", "收费"],
            "city_spots": ["有哪些景点", "有什么景点", "景点推荐", "好玩的地方", "旅游景点"],
            "rating": ["评分", "分", "评价", "多少分", "口碑", "分数"],
            "location": ["在哪里", "位置", "地址", "具体地点", "方位", "在哪儿"],
            "contact": ["联系方式", "电话", "联系电话", "电话号码", "联系我们", "客服电话"],
            "city": ["在哪个城市", "属于哪个城市", "位于哪个城市", "所在城市", "在哪个市"],
            "province": ["在哪个省份", "属于哪个省份", "位于哪个省份", "所在省份", "在哪个省"]
        }
        
        self._init_jieba()
        self.llm_cache = {}
    def _load_spot_dict(self):
        """从数据库加载景点名称词典"""
        spot_names = self.db_manager.get_all_spot_names()
        unique_spots = list({name: None for name in spot_names}.keys())
        return sorted(unique_spots, key=lambda x: len(x), reverse=True)

    def _init_jieba(self):
        """初始化jieba分词，加载景点名称词典"""
        if 'jieba' in globals():
            with open("agent/sql/spot_dict.txt", "w", encoding="utf-8") as f:
                for name in self.spot_dict:
                    f.write(f"{name} 1000\n")
            jieba.load_userdict("agent/sql/spot_dict.txt")

    def process(self, user_question):
        """处理用户问题，识别问题类型并提取关键信息"""
        user_question = user_question.strip().lower()
        logging.info(f"处理用户问题: {user_question}")

        # 1. 附近景点查询
        nearby_keywords = ["附近", "周边", "周围", "旁边", "边上", "近"]
        if any(keyword in user_question for keyword in nearby_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                spot_info = self._get_spot_info(name)
                if spot_info and 'latitude' in spot_info and 'longitude' in spot_info:
                    return {
                        "type": "nearby",
                        "name": name,
                        "latitude": spot_info['latitude'],
                        "longitude": spot_info['longitude'],
                        "radius": self._extract_radius(user_question),
                        "message": user_question
                    }
            return {"type": "unknown", "message": user_question}

        # 2. 营业时间查询
        time_keywords = ["营业时间", "开放时间", "几点开门", "几点关门", "关门时间", "开门时间"]
        if any(keyword in user_question for keyword in time_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "open_time", "name": name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 3. 门票价格查询
        price_keywords = ["门票", "票价", "多少钱", "价格", "费用", "收费"]
        if any(keyword in user_question for keyword in price_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "ticket_price", "name": name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 4. 城市景点查询
        city_keywords = ["有哪些景点", "有什么景点", "景点推荐", "好玩的地方"]
        if any(keyword in user_question for keyword in city_keywords):
            city_name = self._extract_city_name(user_question)
            if city_name:
                return {"type": "city_spots", "city_name": city_name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 5. 评分查询
        rating_keywords = ["评分", "分", "评价", "多少分"]
        if any(keyword in user_question for keyword in rating_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "rating", "name": name, "message": user_question}

        # 6. 位置查询
        location_keywords = ["在哪里", "位置", "地址", "具体地点"]
        if any(keyword in user_question for keyword in location_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "location", "name": name, "message": user_question}

        # 7. 联系方式查询
        contact_keywords = ["联系方式", "电话", "联系电话", "电话号码", "联系我们", "客服电话"]
        if any(keyword in user_question for keyword in contact_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "contact", "name": name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 8. 城市/省份查询
        location_keywords = ["在哪个城市", "在哪个省份", "属于哪个城市", "属于哪个省份", "在哪个市", "在哪个省"]
        if any(keyword in user_question for keyword in location_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                # 使用类属性中的关键词列表
                city_keywords = self.question_types["city"]
                province_keywords = self.question_types["province"]
                
                if any(keyword in user_question for keyword in city_keywords):
                    return {"type": "city", "name": name, "message": user_question}
                elif any(keyword in user_question for keyword in province_keywords):
                    return {"type": "province", "name": name, "message": user_question}
            
            return {"type": "unknown", "message": user_question}
        
        # 9. 景点介绍查询
        intro_keywords = ["介绍", "概况", "简介"]
        if any(keyword in user_question for keyword in intro_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "introduction", "name": name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 10. 交通路线查询
        traffic_keywords = ["怎么去", "交通路线", "路线"]
        if any(keyword in user_question for keyword in traffic_keywords):
            name = self._extract_spot_name(user_question)
            if name:
                return {"type": "traffic", "name": name, "message": user_question}
            return {"type": "unknown", "message": user_question}

        # 11. 其他类型查询
        name = self._extract_spot_name(user_question)
        if name:
            return {"type": "unknown", "name": name, "message": user_question}

        return {"type": "unknown", "message": user_question}

    def _extract_spot_name(self, question):
        """从问题中提取景点名称"""
        # 基于词典的精确匹配（长名称优先）
        for name in self.spot_dict:
            if name.lower() in question and (
                    question.startswith(name.lower() + "的") or
                    question.endswith("的" + name.lower()) or
                    f" {name.lower()} " in f" {question} "
            ):
                return name

        # 分词匹配
        if 'jieba' in globals():
            try:
                words = jieba.cut(question)
                matched_words = [word for word in words if word in self.spot_dict]
                if matched_words:
                    return max(matched_words, key=len)
            except Exception as e:
                logging.error(f"jieba分词出错: {e}")

        return None

    def _extract_radius(self, question):
        """从问题中提取搜索半径（单位：公里），默认5公里"""
        radius_pattern = r"(\d+(?:\.\d+)?)\s*公里"
        match = re.search(radius_pattern, question)

        if match:
            try:
                radius = float(match.group(1))
                return min(radius, 50.0)  # 限制最大半径为50公里
            except ValueError as e:
                logging.error(f"提取半径出错: {e}")

        return 5.0  # 默认搜索半径5公里

    def _extract_city_name(self, question):
        """从问题中提取城市名称"""
        city_keywords = ["有哪些景点", "有什么景点", "景点推荐", "好玩的地方", "的景点"]
        for keyword in city_keywords:
            question = question.replace(keyword, "")

        city_name = question.strip()

        # 处理可能包含省份的情况（如"北京北京"、"北京市北京"）
        if city_name and city_name.startswith("北京"):
            city_name = city_name.replace("北京", "", 1)
            if not city_name:
                city_name = "北京"

        return city_name if city_name else None

    @functools.lru_cache(maxsize=128)
    def _get_spot_info(self, name):
        """查询景点的经纬度信息"""
        return self.db_manager.get_spot_coordinates(name)