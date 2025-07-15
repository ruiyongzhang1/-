"""
PDF生成工具模块
专门用于生成旅行规划PDF报告
"""

import os
import markdown
from datetime import datetime
from typing import Optional

try:
    import pdfkit
except ImportError:
    pdfkit = None
    print("警告: pdfkit 未安装，PDF生成功能不可用")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    reportlab_available = True
except ImportError:
    reportlab_available = False
    print("警告: reportlab 未安装，PDF生成功能受限")


class PDFGeneratorTool:
    """PDF生成工具类"""

    def __init__(self, output_dir: str = None):
        """
        初始化PDF生成器
        
        Args:
            output_dir: PDF输出目录，如果为None则使用默认目录
        """
        if output_dir:
            self.output_dir = output_dir
        else:
            # 使用当前项目目录下的static/pdfs，统一跨平台
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                self.output_dir = os.path.join(project_root, "static", "pdfs")
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_travel_pdf(self, conversation_data: str, summary: str = "", user_info: str = "") -> str:
        """
        生成旅行规划PDF报告
        
        Args:
            conversation_data: 对话内容
            summary: 总结信息
            user_info: 用户信息
            
        Returns:
            str: 生成结果消息
        """
        if not pdfkit:
            return self._generate_fallback_message(conversation_data, summary, user_info)
        try:
            return self._generate_with_wkhtmltopdf(conversation_data, summary, user_info)
        except Exception as e:
            print(f"wkhtmltopdf生成失败: {e}")
            if reportlab_available:
                return self._generate_with_reportlab(conversation_data, summary, user_info)
            else:
                return f"PDF生成失败: {str(e)}"

    def _generate_with_wkhtmltopdf(self, conversation_data: str, summary: str, user_info: str) -> str:
        """使用wkhtmltopdf生成PDF"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"{user_info}_旅行规划_{timestamp}.pdf" if user_info else f"旅行规划_{timestamp}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        # 构建HTML内容
        html_content = self._build_html_content(conversation_data, summary)

        # 配置wkhtmltopdf
        config = self._get_wkhtmltopdf_config()
        
        # 生成PDF选项 - 解决Linux中文乱码问题
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            # Linux字体配置
            'custom-header': [
                ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
            ],
            'disable-smart-shrinking': None,
            'print-media-type': None,
            'load-error-handling': 'ignore',
            'load-media-error-handling': 'ignore'
        }
        
        # 从字符串生成PDF
        if config:
            pdfkit.from_string(html_content, pdf_path, configuration=config, options=options)
        else:
            pdfkit.from_string(html_content, pdf_path, options=options)

        # 返回下载链接
        download_link = f"/static/pdfs/{pdf_filename}"
        return f"PDF已成功生成，您可以通过以下链接下载: <a href='{download_link}' target='_blank'>下载PDF</a>"

    def _generate_with_reportlab(self, conversation_data: str, summary: str, user_info: str) -> str:
        """使用ReportLab生成PDF（备用方案）"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"{user_info}_旅行规划_{timestamp}.pdf" if user_info else f"旅行规划_{timestamp}.pdf"
        pdf_path = os.path.join(self.output_dir, pdf_filename)

        # 创建PDF文档
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        # 添加标题
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=30,
            textColor=HexColor("#210DB3")
        )
        story.append(Paragraph("智能旅行规划报告", title_style))
        story.append(Spacer(1, 12))

        # 添加生成时间
        story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}", styles['Normal']))
        story.append(Spacer(1, 12))

        # 添加总结
        if summary:
            story.append(Paragraph("AI总结报告", styles['Heading2']))
            story.append(Paragraph(summary, styles['Normal']))
            story.append(Spacer(1, 12))

        # 添加对话记录
        story.append(Paragraph("完整对话记录", styles['Heading2']))
        story.append(Paragraph(conversation_data, styles['Normal']))

        # 生成PDF
        doc.build(story)

        # 返回下载链接
        download_link = f"C:/new_py/static/pdfs/{pdf_filename}"
        return f"PDF已成功生成（使用ReportLab），您可以通过以下链接下载: <a href='{download_link}' target='_blank'>下载PDF</a>"

    def _generate_fallback_message(self, conversation_data: str, summary: str, user_info: str) -> str:
        """生成备用文本文件"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = f"{user_info}_旅行规划_{timestamp}.txt" if user_info else f"旅行规划_{timestamp}.txt"
        txt_path = os.path.join(self.output_dir, txt_filename)

        # 构建文本内容
        content = f"""智能旅行规划报告
生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

AI总结概括报告:
{summary if summary else '暂无总结'}
本报告由青鸾向导AI旅行规划系统生成
"""

        # 保存文本文件
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)

        download_link = f"/static/pdfs/{txt_filename}"
        return f"PDF生成功能不可用，已生成文本版本，您可以通过以下链接下载: <a href='{download_link}' target='_blank'>下载文本文件</a>"

    def _build_html_content(self, conversation_data: str, summary: str) -> str:
        """构建HTML内容"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>智能旅行规划报告</title>
            <style>
                body {{ 
                    font-family: 'WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', 'Microsoft YaHei', 'SimSun', 'Arial', sans-serif; 
                    line-height: 1.6;
                    margin: 40px;
                    color: #333;
                }}
                h1, h2, h3 {{ 
                    color: #210DB3; 
                    margin-top: 30px;
                    margin-bottom: 15px;
                }}
                h1 {{ 
                    text-align: center; 
                    border-bottom: 2px solid #4CAF50;
                    padding-bottom: 10px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 15px 0;
                    background: white;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 12px 8px;
                    text-align: left;
                    vertical-align: top;
                    word-wrap: break-word;
                }}
                th {{
                    background: #f8f9fa;
                    font-weight: bold;
                    color: #4CAF50;
                }}
                tr:nth-child(even) {{
                    background: #f9f9f9;
                }}
                pre {{ 
                    background: #f5f5f5; 
                    padding: 15px; 
                    border-radius: 5px; 
                    white-space: pre-wrap; 
                    word-wrap: break-word;
                    border-left: 4px solid #4CAF50;
                }}
                code {{ 
                    background: #eee; 
                    padding: 2px 6px; 
                    border-radius: 3px;
                    font-family: 'Consolas', 'Monaco', monospace;
                }}
                .timestamp {{
                    color: #666;
                    font-style: italic;
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .footer {{
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    text-align: center;
                    color: #888;
                    font-size: 14px;
                }}
                blockquote {{
                    border-left: 4px solid #4CAF50;
                    margin: 15px 0;
                    padding: 10px 20px;
                    background: #f9f9f9;
                }}
                ul, ol {{
                    padding-left: 30px;
                }}
                li {{
                    margin-bottom: 5px;
                }}
            </style>
        </head>
        <body>
            <h1>智能旅行规划报告</h1>
            <div class="timestamp">生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</div>
            
            <h2>📋 AI总结报告</h2>
            <div>
                {markdown.markdown(summary, extensions=['tables', 'fenced_code', 'codehilite']) if summary else '<p>暂无总结信息</p>'}
            </div>
            <div class="footer">
                <p>本报告由青鸾向导AI旅行规划系统生成</p>
            </div>
        </body>
        </html>
        """

    def _get_wkhtmltopdf_config(self) -> Optional[object]:
        """获取wkhtmltopdf配置"""
        possible_paths = [
            r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',  # Windows默认路径
            r'C:\wkhtmltopdf\bin\wkhtmltopdf.exe',
            '/usr/bin/wkhtmltopdf',  # Linux默认路径
            '/usr/local/bin/wkhtmltopdf',  # Mac默认路径
            'wkhtmltopdf'  # 系统PATH中
        ]
        
        for path in possible_paths:
            if os.path.exists(path) or path == 'wkhtmltopdf':
                try:
                    return pdfkit.configuration(wkhtmltopdf=path)
                except Exception:
                    continue
        
        # 如果都不存在，尝试不指定路径
        return None

    def get_output_dir(self) -> str:
        """获取输出目录"""
        return self.output_dir

    def set_output_dir(self, output_dir: str):
        """设置输出目录"""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)


# PDF生成相关的工具函数
def generate_pdf_content(conversation_data: str, summary: str = "", user_info: str = "", output_dir: str = None) -> str:
    """
    便捷的PDF生成函数
    
    Args:
        conversation_data: 对话内容
        summary: 总结信息
        user_info: 用户信息
        output_dir: 输出目录
        
    Returns:
        str: 生成结果消息
    """
    generator = PDFGeneratorTool(output_dir)
    return generator.generate_travel_pdf(conversation_data, summary, user_info)


def check_pdf_dependencies() -> dict:
    """
    检查PDF生成所需的依赖
    
    Returns:
        dict: 依赖检查结果
    """
    result = {
        'pdfkit': pdfkit is not None,
        'reportlab': reportlab_available,
        'markdown': True,  # markdown是必需的，已在顶部导入
        'wkhtmltopdf_available': False
    }
    
    if pdfkit:
        try:
            generator = PDFGeneratorTool()
            config = generator._get_wkhtmltopdf_config()
            result['wkhtmltopdf_available'] = config is not None
        except Exception:
            result['wkhtmltopdf_available'] = False
    
    return result


if __name__ == "__main__":
    # 测试代码
    test_conversation = """
    用户: 我想去日本旅行，有什么推荐吗？
    助手: 日本是个很棒的旅行目的地！我为您推荐以下几个地方：
    
    ## 推荐城市
    1. **东京** - 现代化大都市，购物和美食天堂
    2. **京都** - 传统文化古都，寺庙和花园
    3. **大阪** - 美食之都，关西文化中心
    
    ## 最佳旅行时间
    - 春季（3-5月）：樱花季节
    - 秋季（9-11月）：红叶季节
    """
    
    test_summary = """
    ## 旅行总结
    - 目的地：日本
    - 推荐城市：东京、京都、大阪
    - 最佳时间：春季或秋季
    - 特色：樱花、红叶、美食、文化
    """
    
    # 检查依赖
    deps = check_pdf_dependencies()
    print("依赖检查结果:", deps)
    
    # 生成测试PDF
    result = generate_pdf_content(test_conversation, test_summary, "test_user")
    print("生成结果:", result)
