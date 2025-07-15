class ResponseGenerator:
    def __init__(self):
        pass

    def generate(self, processed_questions, db_results):
        """生成用户问题的回答"""
        if not db_results:
            return ""
        
        # 检查问题类型
        question_types = [q["type"] for q in processed_questions]
        
        # 优先处理景点信息查询
        if "spot_info" in question_types:
            return self._generate_spot_info_response(processed_questions, db_results)
            
        # 处理城市景点查询或复合查询
        elif "city_spots" in question_types or "compound_filter" in question_types:
            return self._generate_city_spots_response(processed_questions, db_results)
        
        # 处理附近景点推荐查询
        elif "nearby_spots" in question_types:
            return self._generate_nearby_spots_response(processed_questions, db_results)
        
        # 通用响应
        return self._generate_generic_response(processed_questions, db_results)

    def _generate_city_spots_response(self, processed_questions, db_results):
        """生成城市景点查询的响应，包含营业时间和电话信息"""
        # 尝试提取城市名称
        city_name = None
        for question in processed_questions:
            if question["type"] == "city_spots":
                city_name = question.get("city_name")
                break
            elif question["type"] == "compound_filter":
                for keyword in question.get("keywords", []):
                    if keyword["type"] == "city_spots":
                        city_name = keyword.get("city_name")
                        break
                if city_name:
                    break
        
        # 构建响应
        response = f"{city_name} 的推荐景点有：\n"
        for i, spot in enumerate(db_results[:10], 1):  # 只显示前10个景点
            # 处理价格信息，直接显示"缺失"
            cost = spot['cost']
            price = "缺失"
            if cost is not None:
                price = f"{cost}元" if cost > 0 else "免费"
            
            response += f"{i}. {spot['name']}（评分：{spot['rating']}，价格：{price}）\n"
            response += f"   类型：{spot['type']}\n"
            response += f"   地址：{spot['address']}\n"
            
            # 添加营业时间信息
            if spot['opentime_today']:
                response += f"   营业时间：{spot['opentime_today']}\n"
            elif spot['open_time_start'] and spot['open_time_end']:
                # 从timedelta对象转换为HH:MM格式
                start_time = self._format_time(spot['open_time_start'])
                end_time = self._format_time(spot['open_time_end'])
                response += f"   营业时间：{start_time}-{end_time}\n"
            
            # 添加电话信息（格式化电话号码）
            if spot['tel']:
                # 简单格式化，实际可能需要更复杂的处理
                tel = self._format_phone(spot['tel'])
                response += f"   电话：{tel}\n"
        
        return response

    def _generate_spot_info_response(self, processed_questions, db_results):
        """生成景点信息查询的响应"""
        spot_name = None
        attributes = []
        for question in processed_questions:
            if question["type"] == "spot_info":
                spot_name = question.get("spot_name")
                attributes = question.get("attributes", [])
                break

        response = f"{spot_name} 的相关信息如下：\n"
        for result in db_results:
            if "评分" in attributes and 'rating' in result:
                response += f"评分：{result['rating']}\n"
            if "位置" in attributes and 'address' in result:
                response += f"位置：{result['address']}\n"
            if "电话" in attributes and 'tel' in result:
                tel = self._format_phone(result['tel'])
                response += f"电话：{tel}\n"
            if "营业时间" in attributes:
                if 'opentime_today' in result and result['opentime_today']:
                    response += f"营业时间：{result['opentime_today']}\n"
                elif 'open_time_start' in result and 'open_time_end' in result and result['open_time_start'] and result['open_time_end']:
                    start_time = self._format_time(result['open_time_start'])
                    end_time = self._format_time(result['open_time_end'])
                    response += f"营业时间：{start_time}-{end_time}\n"
            if "所在城市" in attributes and 'name' in result:
                response += f"所在城市：{result['name']}\n"
        return response

    def _generate_nearby_spots_response(self, processed_questions, db_results):
        """生成附近景点推荐查询的响应，包含距离信息"""
        spot_name = None
        for question in processed_questions:
            if question["type"] == "nearby_spots":
                spot_name = question.get("spot_name")
                break

        response = f"{spot_name} 附近评分最高的5个景点有：\n"
        for i, spot in enumerate(db_results[:5], 1):  # 只显示前5个景点
            # 处理价格信息，直接显示"缺失"
            cost = spot['cost']
            price = "缺失"
            if cost is not None:
                price = f"{cost}元" if cost > 0 else "免费"
            
            # 处理距离信息
            distance = spot.get('distance', None)
            distance_str = "距离未知"
            if distance is not None:
                if distance < 1:
                    distance_str = f"{int(distance * 1000)}米"
                else:
                    distance_str = f"{distance:.1f}公里"
            
            response += f"{i}. {spot['name']}（评分：{spot['rating']}，价格：{price}，距离：{distance_str}）\n"
            response += f"   类型：{spot['type']}\n"
            response += f"   地址：{spot['address']}\n"
            
            # 添加营业时间信息
            if spot['opentime_today']:
                response += f"   营业时间：{spot['opentime_today']}\n"
            elif spot['open_time_start'] and spot['open_time_end']:
                # 从timedelta对象转换为HH:MM格式
                start_time = self._format_time(spot['open_time_start'])
                end_time = self._format_time(spot['open_time_end'])
                response += f"   营业时间：{start_time}-{end_time}\n"
            
            # 添加电话信息（格式化电话号码）
            if spot['tel']:
                # 简单格式化，实际可能需要更复杂的处理
                tel = self._format_phone(spot['tel'])
                response += f"   电话：{tel}\n"
        
        return response

    def _format_time(self, timedelta_obj):
        """将timedelta对象格式化为HH:MM字符串"""
        if not timedelta_obj:
            return "未知"
            
        hours, remainder = divmod(timedelta_obj.seconds, 3600)
        minutes = remainder // 60
        return f"{hours:02d}:{minutes:02d}"

    def _format_phone(self, phone_str):
        """格式化电话号码，提高可读性"""
        if not phone_str:
            return "未知"
        
        # 尝试分割多个电话号码
        phones = phone_str.split()
        if len(phones) > 1:
            return "；".join(phones)
        
        # 尝试格式化单个号码
        if len(phone_str) >= 7:
            return f"{phone_str[:3]}-{phone_str[3:7]}-{phone_str[7:]}"
        
        return phone_str

    def _generate_generic_response(self, processed_questions, db_results):
        """生成通用响应"""
        response = "查询结果如下：\n"
        for i, result in enumerate(db_results[:10], 1):  # 只显示前10个结果
            # 处理价格信息，直接显示"缺失"
            cost = result['cost']
            price = "缺失"
            if cost is not None:
                price = f"{cost}元" if cost > 0 else "免费"
            
            response += f"{i}. {result['name']}（评分：{result['rating']}，价格：{price}）\n"
            response += f"   地址：{result['address']}\n"
            
            # 添加营业时间和电话信息
            if result['opentime_today']:
                response += f"   营业时间：{result['opentime_today']}\n"
            elif result['open_time_start'] and result['open_time_end']:
                start_time = self._format_time(result['open_time_start'])
                end_time = self._format_time(result['open_time_end'])
                response += f"   营业时间：{start_time}-{end_time}\n"
            
            if result['tel']:
                tel = self._format_phone(result['tel'])
                response += f"   电话：{tel}\n"
        
        return response