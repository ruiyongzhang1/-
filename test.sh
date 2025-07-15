#!/bin/bash
# 青鸾向导 - Linux字体安装脚本
# 解决wkhtmltopdf中文乱码问题

echo "=========================================="
echo "    安装中文字体 - 解决PDF乱码问题"
echo "=========================================="

# 检测系统类型
if [ -f /etc/debian_version ]; then
    echo "检测到Debian/Ubuntu系统"
    SYSTEM_TYPE="debian"
elif [ -f /etc/redhat-release ]; then
    echo "检测到CentOS/RHEL系统"
    SYSTEM_TYPE="redhat"
else
    echo "未知系统类型，尝试通用安装"
    SYSTEM_TYPE="unknown"
fi

# 安装字体包
install_fonts() {
    echo "安装中文字体包..."
    
    if [ "$SYSTEM_TYPE" = "debian" ]; then
        # Ubuntu/Debian系统
        sudo apt-get update
        sudo apt-get install -y \
            fonts-wqy-zenhei \
            fonts-wqy-microhei \
            fonts-noto-cjk \
            fonts-arphic-ukai \
            fonts-arphic-uming \
            xfonts-wqy
    elif [ "$SYSTEM_TYPE" = "redhat" ]; then
        # CentOS/RHEL系统
        sudo yum install -y \
            wqy-zenhei-fonts \
            wqy-microhei-fonts \
            google-noto-cjk-fonts
    else
        echo "请手动安装中文字体包"
        echo "Ubuntu/Debian: sudo apt-get install fonts-wqy-zenhei"
        echo "CentOS/RHEL: sudo yum install wqy-zenhei-fonts"
    fi
}

# 创建字体目录
create_font_dirs() {
    echo "创建字体目录..."
    sudo mkdir -p /usr/share/fonts/chinese
    sudo mkdir -p ~/.fonts
}

# 下载并安装字体文件
download_fonts() {
    echo "下载字体文件..."

    # 创建临时目录
    TEMP_DIR=$(mktemp -d)
    cd $TEMP_DIR

    # 下载字体压缩包（文泉驿正黑）
    echo "从 SourceForge 下载文泉驿正黑字体..."
    wget https://downloads.sourceforge.net/project/wqy/wqy-zenhei/0.9.45/wqy-zenhei-0.9.45.tar.gz

    # 解压字体包
    echo "解压字体..."
    tar -zxvf wqy-zenhei-0.9.45.tar.gz

    # 进入字体目录
    cd wqy-zenhei

    # 复制字体到系统字体目录
    echo "复制字体到系统字体目录..."
    sudo cp wqy-zenhei.ttc /usr/share/fonts/
    
    # 如果用户字体目录存在，也复制过去
    mkdir -p ~/.fonts
    cp wqy-zenhei.ttc ~/.fonts/

    # 更新字体缓存
    echo "更新字体缓存..."
    sudo fc-cache -fv
    fc-cache -fv

    # 清理临时目录
    echo "清理临时文件..."
    cd ~
    rm -rf "$TEMP_DIR"

    echo "字体安装完成。"
}

# 配置wkhtmltopdf
configure_wkhtmltopdf() {
    echo "配置wkhtmltopdf..."
    
    # 创建配置文件
    cat > ~/.wkhtmltopdf.conf << EOF
# wkhtmltopdf配置文件
--encoding UTF-8
--page-size A4
--margin-top 10mm
--margin-right 10mm
--margin-bottom 10mm
--margin-left 10mm
--enable-local-file-access
--disable-smart-shrinking
--print-media-type
--no-outline
--disable-javascript
--load-error-handling ignore
--load-media-error-handling ignore
--custom-header "User-Agent" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
EOF
}

# 测试字体安装
test_fonts() {
    echo "测试字体安装..."
    
    # 检查字体是否安装成功
    fc-list | grep -i "wqy\|noto\|chinese" | head -5
    
    # 创建测试HTML
    cat > test_font.html << EOF
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>字体测试</title>
    <style>
        body { font-family: "WenQuanYi Zen Hei", "Microsoft YaHei", sans-serif; }
        .test { font-size: 24px; margin: 20px; }
    </style>
</head>
<body>
    <div class="test">中文测试：青鸾向导</div>
    <div class="test">English Test: QL Guide</div>
    <div class="test">数字测试：123456</div>
</body>
</html>
EOF
    
    # 测试PDF生成
    wkhtmltopdf test_font.html test_font.pdf
    
    if [ -f test_font.pdf ]; then
        echo "✅ PDF生成成功，请检查test_font.pdf文件"
    else
        echo "❌ PDF生成失败"
    fi
}

# 主函数
main() {
    install_fonts
    create_font_dirs
    download_fonts
    configure_wkhtmltopdf
    test_fonts
    
    echo "=========================================="
    echo "字体安装完成！"
    echo "如果仍有问题，请检查："
    echo "1. 系统语言环境设置"
    echo "2. wkhtmltopdf版本"
    echo "3. HTML文件编码"
    echo "=========================================="
}

# 执行主函数
main