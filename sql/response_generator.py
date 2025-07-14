class ResponseGenerator:

    UNABLE_TO_ANSWER = "抱歉，暂时无法回答这个问题。"
    def generate(self, processed_question, db_results):
        """根据处理后的问题和数据库结果生成用户响应"""
        query_type = processed_question.get("type")
        message = processed_question.get("message")

        if not db_results:
            return self.UNABLE_TO_ANSWER

        # 1. 附近景点查询
        if query_type == "nearby":
            spot_name = processed_question.get("name")
            radius = processed_question.get("radius", 5.0)
            response = f"{spot_name}附近{radius}公里内的景点有：\n"

            for i, spot in enumerate(db_results, 1):
                distance = round(spot['distance'], 2)
                rating = spot['rating'] or "暂无评分"
                response += f"{i}. {spot['name']}（{spot['type']}，距离{distance}公里，评分{rating}）\n"

            return response

        # 2. 营业时间查询
        elif query_type == "open_time":
            spot = db_results[0]
            name = spot['name']

            if spot['opentime_today']:
                return f"{name}今日营业时间：{spot['opentime_today']}"

            if spot['opentime_week']:
                return f"{name}的营业时间：{spot['opentime_week']}"

            if spot['open_time_start'] and spot['open_time_end']:
                start_time = str(spot['open_time_start'])
                end_time = str(spot['open_time_end'])
                return f"{name}的营业时间为每天{start_time}至{end_time}。"

            return self.UNABLE_TO_ANSWER

        # 3. 门票价格查询
        elif query_type == "ticket_price":
            spot = db_results[0]
            name = spot['name']
            cost = spot['cost']

            if cost is not None:
                return f"{name}的门票价格为{cost}元。"
            else:
                return self.UNABLE_TO_ANSWER

        # 4. 城市景点查询
        elif query_type == "city_spots":
            city_name = processed_question.get("city_name")

            # 调试输出
            print(f"生成城市景点响应，结果数量: {len(db_results)}")
            if db_results and len(db_results) > 0:
                print(f"第一条结果字段: {list(db_results[0].keys())}")

            if not db_results:
                return self.UNABLE_TO_ANSWER

            # 检查结果是否包含城市和省份信息
            has_location_info = all(
                key in db_results[0] for key in ['city_name', 'province_name']
            )

            response = f"{city_name}的推荐景点有：\n"
            for i, spot in enumerate(db_results, 1):
                rating = spot.get('rating', "暂无评分")  # 使用get方法避免KeyError
                spot_type = spot.get('type', "未知类型")
                response += f"{i}. {spot['name']}（{spot_type}，评分{rating}）\n"

            return response

        # 5. 评分查询
        elif query_type == "rating":
            spot = db_results[0]
            return f"{spot['name']}的评分为：{spot['rating']}分"

        # 6. 位置查询
        elif query_type == "location":
            spot = db_results[0]
            name = spot['name']
            address = spot.get("address", "")
            city = spot.get("city_name", "")
            province = spot.get("province_name", "")

            if province and city and address:
                return f"{name}位于{province}{city}{address}。"
            elif province and city:
                return f"{name}位于{province}{city}。"
            elif address:
                return f"{name}的地址是{address}。"
            else:
                return self.UNABLE_TO_ANSWER

        # 8. 联系方式查询
        elif query_type == "contact":
            if not db_results:
                return self.UNABLE_TO_ANSWER

            spot = db_results[0]
            tel = spot.get('tel')
            if tel:
                return f"{spot['name']}的联系电话是：{tel}"
            else:
                return self.UNABLE_TO_ANSWER

        # 9. 城市查询
        elif query_type == "city":
            if not db_results:
                return self.UNABLE_TO_ANSWER

            spot = db_results[0]
            city_name = spot.get('city_name')
            if city_name:
                return f"{spot['name']}位于{city_name}。"
            else:
                return self.UNABLE_TO_ANSWER

        # 10. 省份查询
        elif query_type == "province":
            if not db_results:
                return self.UNABLE_TO_ANSWER

            spot = db_results[0]
            province_name = spot.get('province_name')
            if province_name:
                return f"{spot['name']}位于{province_name}。"
            else:
                return self.UNABLE_TO_ANSWER

        # 其他类型查询
        return self.UNABLE_TO_ANSWER