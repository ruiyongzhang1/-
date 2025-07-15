#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片代理服务 - 简化版，专注于直接URL展示
"""

import requests
from flask import Response
import io
from PIL import Image
import base64

class ImageProxyService:
    """图片代理服务类 - 简化版"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 禁用SSL警告（在代理环境下）
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def proxy_image(self, image_url: str) -> Response:
        """代理获取图片并返回Flask响应"""
        try:
            # 下载图片
            response = self.session.get(image_url, timeout=30, stream=True, verify=False)
            response.raise_for_status()
            
            # 读取图片数据
            image_data = response.content
            
            # 验证是否是有效图片
            try:
                img = Image.open(io.BytesIO(image_data))
                img.verify()
            except Exception:
                return Response("Invalid image", status=400, mimetype='text/plain')
            
            # 返回图片响应
            return Response(
                image_data,
                mimetype=response.headers.get('Content-Type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=3600',  # 缓存1小时
                    'Content-Length': str(len(image_data))
                }
            )
            
        except requests.exceptions.RequestException as e:
            print(f"图片代理错误: {e}")
            return Response(f"Failed to fetch image: {str(e)}", status=500, mimetype='text/plain')
        except Exception as e:
            print(f"图片处理错误: {e}")
            return Response(f"Image processing error: {str(e)}", status=500, mimetype='text/plain')
    
    def generate_placeholder_svg_base64(self, attraction_name: str) -> str:
        """生成SVG占位图片的base64编码"""
        try:
            svg_placeholder = f'''<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
<rect width="400" height="300" fill="#f0f0f0" stroke="#ccc"/>
<text x="200" y="140" text-anchor="middle" fill="#666" font-size="16">{attraction_name}</text>
<text x="200" y="160" text-anchor="middle" fill="#666" font-size="14">景点图片</text>
<text x="200" y="180" text-anchor="middle" fill="#999" font-size="12">图片加载失败</text>
</svg>'''
            
            svg_base64 = base64.b64encode(svg_placeholder.encode('utf-8')).decode('utf-8')
            return f"data:image/svg+xml;base64,{svg_base64}"
            
        except Exception as e:
            print(f"生成SVG占位图片失败: {e}")
            return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2YwZjBmMCIgc3Ryb2tlPSIjY2NjIi8+PHRleHQgeD0iMjAwIiB5PSIxNTAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiM2NjYiIGZvbnQtc2l6ZT0iMTYiPuaZr+eCueWbvueJhzwvdGV4dD48L3N2Zz4="

# 全局实例
image_proxy_service = ImageProxyService()
