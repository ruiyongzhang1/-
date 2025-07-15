// 旅行页面专用JavaScript

let currentPlan = null;
let isPlanning = false;
let conversationHistory = [];

// 处理偏好标签选择
document.addEventListener('DOMContentLoaded', function() {
    // 初始隐藏PDF导出按钮
    document.getElementById('exportPdfBtn').style.display = 'none';
    
    document.querySelectorAll('.preference-tags').forEach(container => {
        container.addEventListener('click', function(e) {
            if (e.target.classList.contains('preference-tag')) {
                e.target.classList.toggle('selected');
            }
        });
    });
    
    // 设置最小日期为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('start_date').min = today;
    document.getElementById('end_date').min = today;
    
    // 初始化日期值
    initializeDates();
    
    // 确保结束日期不早于开始日期
    document.getElementById('start_date').addEventListener('change', function() {
        const startDate = this.value;
        document.getElementById('end_date').min = startDate;
        if (document.getElementById('end_date').value < startDate) {
            document.getElementById('end_date').value = startDate;
        }
    });
    
    // 表单提交
    document.getElementById('travelForm').addEventListener('submit', function(e) {
        e.preventDefault();
        if (isPlanning) return;
        
        // 收集表单数据
        const formData = {
            source: document.getElementById('source').value,
            destination: document.getElementById('destination').value,
            start_date: document.getElementById('start_date').value,
            end_date: document.getElementById('end_date').value,
            budget_per_person: parseInt(document.getElementById('budget').value),
            travelers: parseInt(document.getElementById('traveler_count').value),
            accommodation_type: document.getElementById('accommodation_type').value,
            preferences: Array.from(document.querySelectorAll('#preferences .preference-tag.selected')).map(tag => tag.dataset.value),
            transportation_mode: Array.from(document.querySelectorAll('#transportation .preference-tag.selected')).map(tag => tag.dataset.value),
            dietary_restrictions: Array.from(document.querySelectorAll('#dietary_restrictions .preference-tag.selected')).map(tag => tag.dataset.value)
        };
        
        // 验证必填字段
        if (!formData.source || !formData.destination || !formData.start_date || !formData.end_date || !formData.budget_per_person || !formData.travelers || !formData.accommodation_type) {
            alert('请填写所有必填信息！');
            return;
        }
        
        if (formData.preferences.length === 0) {
            alert('请至少选择一个旅行偏好！');
            return;
        }
        
        // 验证旅行人数
        if (formData.travelers < 1 || formData.travelers > 20) {
            alert('旅行人数必须在1-20人之间！');
            return;
        }

        // 验证人均预算合理性
        if (formData.budget_per_person < 500) {
            if (!confirm(`人均预算仅为 ${formData.budget_per_person} 元，可能无法提供高质量的旅行方案。是否继续？`)) {
                return;
            }
        }

        if (formData.transportation_mode.length === 0) {
            formData.transportation_mode = ['公共交通'];
        }
        
        if (formData.dietary_restrictions.length === 0) {
            formData.dietary_restrictions = ['无特殊要求'];
        }
        
        startTravelPlanning(formData);
    });
    
    // 回车发送消息
    document.getElementById('message-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 为景点输入框添加回车键监听
    const attractionInput = document.getElementById('attractionInput');
    if (attractionInput) {
        attractionInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                startAttractionGuideFromModal();
            }
        });
    }
});

// 初始化日期值
function initializeDates() {
    const today = new Date();
    const startDate = new Date(today);
    const endDate = new Date(today);
    
    // 出发日期设置为明天
    startDate.setDate(today.getDate() + 1);
    
    // 返回日期设置为出发日期后7天
    endDate.setDate(startDate.getDate() + 7);
    
    // 格式化日期为 YYYY-MM-DD
    const formatDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };
    
    // 设置初始值
    document.getElementById('start_date').value = formatDate(startDate);
    document.getElementById('end_date').value = formatDate(endDate);
}

// 格式化旅行请求
function formatTravelRequest(formData) {
    const totalBudget = formData.budget_per_person * formData.travelers;
    return `🧳 **旅行规划请求**

**基本信息：**
- 📍 出发地：${formData.source}
- 🎯 目的地：${formData.destination}  
- 📅 旅行日期：${formData.start_date} 至 ${formData.end_date}
- 💰 人均预算：￥${formData.budget_per_person} 人民币（总预算约 ${totalBudget} 人民币）
- 👥 旅行人数：${formData.travelers}人
- 🏨 住宿偏好：${formData.accommodation_type}

**旅行偏好：** ${formData.preferences.join(', ')}
**交通方式：** ${formData.transportation_mode.join(', ')}
**饮食要求：** ${formData.dietary_restrictions.join(', ')}`;
}

// 快速提问
function askQuickQuestion(question) {
    if (!currentPlan) {
        alert('请先制定旅行计划！');
        return;
    }
    
    document.getElementById('message-input').value = question;
    sendMessage();
}

// 显示"加载中"动画 - 全新实现
function addTravelLoader() {
    const chatBox = document.getElementById('chat-box');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';   
    typingDiv.innerHTML = '<span></span><span></span><span></span>';
    chatBox.appendChild(typingDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return typingDiv;
}


// ====================== 旅行规划主入口 ======================
function startTravelPlanning(formData) {
  isPlanning = true;

  /* ---------- UI 准备 ---------- */
  const planButton   = document.getElementById('planButton');
  const messageInput = document.getElementById('message-input');
  const sendBtn      = document.getElementById('send-btn1');

  planButton.textContent = '⏳ 正在制定计划...';
  planButton.disabled    = true;
  planButton.classList.add('loading');

  const loadingDots = addTravelLoader();           // “...” 动画

  /* ---------- 发请求 ---------- */
  fetch('/plan_travel', {
    method : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body   : JSON.stringify(formData)
  })
  .then(res => {
    if (!res.ok) throw new Error('网络错误');

    loadingDots.remove();                          // 关掉 “...”
    const planBubble = addMessage('', false);      // 规划气泡
    const planBody   = planBubble.querySelector('.message-content');

    /* ====== 准备流读取 ====== */
    const reader   = res.body.getReader();
    const decoder  = new TextDecoder();
    let   buffer   = '';            // 存放拆包残余
    let   planText = '';            // 行程规划正文
    let   infoText = '';            // 暂存信息收集全文

    /* -- 处理单条 SSE 事件 -- */
    function consume(evt) {
      /* 信息收集，只缓存 */
      if (evt.info_collection_result) {
        infoText = evt.info_collection_result;
        return;
      }
      /* 行程规划流 */
      if (evt.chunk) {
        planText += evt.chunk;
        planBody.innerHTML = marked.parse(planText);
        planBody.scrollTop = planBody.scrollHeight;
        return;
      }
      /* 错误 */
      if (evt.error) {
        planBody.innerHTML =
          `<div style="color:red;">错误：${evt.error}</div>`;
      }
    }

    /* -- 递归读取流 -- */
    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) {
          /* ========== 全部结束，插入信息收集卡片 ========== */
          if (infoText) {
            const infoBubble = addMessage('', false);
            infoBubble.classList.add('info-collector');
            infoBubble.querySelector('.message-content').innerHTML =
              marked.parse(infoText);
          }

          /* UI 收尾 */
          currentPlan = planText;
          isPlanning  = false;
          planButton.textContent = '✨ 重新制定计划';
          planButton.disabled    = false;
          planButton.classList.remove('loading');
          messageInput.disabled  = false;
          sendBtn.disabled       = false;
          document.getElementById('exportPdfBtn').style.display = 'inline-block';
          return;
        }

        /* 拆分 \n\n 事件边界 */
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx).trim();
          buffer    = buffer.slice(idx + 2);

          if (!raw) continue; // ping

          try {
            const evt = raw.startsWith('data:')
              ? JSON.parse(raw.slice(5).trim())
              : JSON.parse(raw);
            consume(evt);
          } catch (e) {
            console.error('JSON 解析失败', e, raw);
          }
        }
        pump();   // 继续读
      });
    }
    pump();       // ⬅️ 启动
  })
  .catch(err => {
    console.error('规划出错:', err);
    loadingDots.remove();
    addMessage(`<div style="color:red;">规划过程中出现错误：${err.message}</div>`, false);

    isPlanning = false;
    planButton.textContent = '✨ 重新制定计划';
    planButton.disabled    = false;
    planButton.classList.remove('loading');
    document.getElementById('exportPdfBtn').style.display = 'none';
  });
}

// 发送消息
function sendMessage() {
    const messageInput = document.getElementById('message-input');
    const message = messageInput.value.trim();
    
    if (!message || isPlanning) return;
    
    messageInput.value = '';
    addMessage(message, true);
    
    // 添加三点式加载动画
    const loadingMessage = addTravelLoader();
    
    fetch('/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: message,
            agent_type: 'travel'
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('网络错误');
        }
        
        // 移除加载消息
        loadingMessage.remove();
        
        // 创建响应消息容器
        const responseDiv = addMessage('', false);
        const contentDiv = responseDiv.querySelector('.message-content');
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';
        
        function readStream() {
            reader.read().then(({done, value}) => {
                if (done) {
                    // 添加到对话历史
                    conversationHistory.push({
                        content: message,
                        isUser: true
                    });
                    conversationHistory.push({
                        content: responseText,
                        isUser: false
                    });
                    
                    // 显示PDF导出按钮
                    document.getElementById('exportPdfBtn').style.display = 'inline-block';
                    return;
                }
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) {
                                responseText += data.chunk;
                                contentDiv.innerHTML = marked.parse(responseText);
                                contentDiv.scrollTop = contentDiv.scrollHeight;
                            } else if (data.error) {
                                contentDiv.innerHTML = `<div style="color: red;">错误: ${data.error}</div>`;
                                return;
                            }
                        } catch (e) {
                            console.log('解析数据出错:', e);
                        }
                    }
                }
                
                readStream();
            });
        }
        
        readStream();
    })
    .catch(error => {
        console.error('发送消息出错:', error);
        loadingMessage.remove();
        addMessage(`<div style="color: red;">发送失败: ${error.message}</div>`, false);
        
        // 确保PDF导出按钮在错误时保持隐藏
        document.getElementById('exportPdfBtn').style.display = 'none';
    });
}

// 添加消息到聊天区域
function addMessage(content, isUser) {
    const chatBox = document.getElementById('chat-box');
    const messageDiv = document.createElement('div');
    
    // 添加基本消息类和特定类型类
    messageDiv.className = isUser ? 'message user-message' : 'message ai-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (isUser) {
        contentDiv.innerHTML = marked.parse(content);
    } else {
        contentDiv.innerHTML = content;
    }
    
    messageDiv.appendChild(contentDiv);
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    return messageDiv;
}

// PDF导出功能
function exportToPDF() {
    if (conversationHistory.length === 0) {
        alert('没有对话内容可导出！');
        return;
    }
    
    // 显示加载状态
    const exportBtn = document.getElementById('exportPdfBtn');
    const originalText = exportBtn.innerHTML;
    exportBtn.innerHTML = '⏳ 正在生成PDF...';
    exportBtn.disabled = true;
    
    // 构建对话内容
    let conversationText = "";
    for (let i = 0; i < conversationHistory.length; i++) {
        const message = conversationHistory[i];
        if (message.isUser) {
            conversationText += `用户: ${message.content}\n\n`;
        } else {
            conversationText += `AI助手: ${message.content}\n\n`;
        }
    }
    
    // 发送给AI进行总结和PDF生成
    //const pdfRequest = `总结以上所有对话，并生成PDF。对话内容如下：\n\n${conversationText}`;
    const pdfRequest =`总结以上所有对话，并生成PDF。`;
    // 添加用户请求消息
    addMessage(pdfRequest, true);
    
    // 添加三点式加载动画
    const loadingMessage = addTravelLoader();
    
    fetch('/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: pdfRequest,
            agent_type: 'pdf_generator'
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('网络错误');
        }
        
        // 移除加载消息
        loadingMessage.remove();
        
        // 创建响应消息容器
        const responseDiv = addMessage('', false);
        const contentDiv = responseDiv.querySelector('.message-content');
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';
        
        function readStream() {
            reader.read().then(({done, value}) => {
                if (done) {
                    // 恢复按钮状态
                    exportBtn.innerHTML = originalText;
                    exportBtn.disabled = false;
                    return;
                }
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) {
                                responseText += data.chunk;
                                contentDiv.innerHTML = marked.parse(responseText);
                                contentDiv.scrollTop = contentDiv.scrollHeight;
                            } else if (data.error) {
                                contentDiv.innerHTML = `<div style="color: red;">错误: ${data.error}</div>`;
                                exportBtn.innerHTML = originalText;
                                exportBtn.disabled = false;
                                return;
                            }
                        } catch (e) {
                            console.log('解析数据出错:', e);
                        }
                    }
                }
                
                readStream();
            });
        }
        
        readStream();
    })
    .catch(error => {
        console.error('PDF导出错误:', error);
        alert('PDF生成失败: ' + error.message);
        
        // 恢复按钮状态
        exportBtn.innerHTML = originalText;
        exportBtn.disabled = false;
        loadingMessage.remove();    
    });
} 

// 显示景点讲解对话框
function showAttractionGuideDialog() {
    const modal = document.getElementById('attractionGuideModal');
    modal.style.display = 'flex';
    
    // 添加动画类
    setTimeout(() => {
        modal.classList.add('show');
    }, 10);
    
    // 聚焦到输入框
    setTimeout(() => {
        document.getElementById('attractionInput').focus();
    }, 300);
}

// 关闭景点讲解对话框
function closeAttractionGuideDialog() {
    const modal = document.getElementById('attractionGuideModal');
    
    // 移除动画类
    modal.classList.remove('show');
    
    // 等待动画完成后隐藏
    setTimeout(() => {
        modal.style.display = 'none';
        
        // 清空输入框
        document.getElementById('attractionInput').value = '';
        document.getElementById('guideStyleSelect').selectedIndex = 0;
    }, 300);
}

// 从对话框开始景点讲解
function startAttractionGuideFromModal() {
    const attractionInput = document.getElementById('attractionInput');
    const guideStyleSelect = document.getElementById('guideStyleSelect');
    const generateImageCheckbox = document.getElementById('generateImageCheckbox');
    
    const attractionName = attractionInput.value.trim();
    const style = guideStyleSelect.value;
    const generateImage = generateImageCheckbox.checked;
    
    if (!attractionName) {
        alert('请输入要了解的景点名称');
        return;
    }
    
    // 关闭对话框
    closeAttractionGuideDialog();
    
    // 构建查询消息
    const guideMessage = `请用${style}风格详细介绍${attractionName}景点，包括历史背景、文化意义、建筑特色、参观建议等信息。`;
    const imageOption = generateImage ? "✅ 已启用图片生成" : "❌ 已禁用图片生成";
    const userRequestContent = `🏛️ **景点讲解请求**\n\n**景点名称**: ${attractionName}\n**讲解风格**: ${style}\n**图片生成**: ${imageOption}\n\n正在为您生成专业的景点讲解...`;
    
    // 添加用户请求消息
    addMessage(userRequestContent, true);
    
    // 添加加载动画
    const loadingMessage = addTravelLoader();
    
    // 发送景点讲解请求
    fetch('/attraction_guide', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message: guideMessage,
            generate_image: generateImage
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('网络错误');
        }
        
        // 移除加载动画
        loadingMessage.remove();
        
        // 创建响应消息容器
        const responseDiv = addMessage('', false);
        const contentDiv = responseDiv.querySelector('.message-content');
        
        // 处理流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';
        
        function readStream() {
            reader.read().then(({ done, value }) => {
                if (done) {
                    console.log('景点讲解完成');
                    
                    // 保存到对话历史
                    conversationHistory.push({ content: userRequestContent, isUser: true });
                    conversationHistory.push({ content: responseText, isUser: false });

                    // 启用聊天输入
                    const messageInput = document.getElementById('message-input');
                    const sendBtn = document.getElementById('send-btn1');
                    messageInput.disabled = false;
                    sendBtn.disabled = false;
                    messageInput.placeholder = "对景点讲解有什么问题吗？可以继续提问...";
                    return;
                }
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.chunk) {
                                responseText += data.chunk;
                                contentDiv.innerHTML = marked.parse(responseText);
                                const chatBox = document.getElementById('chat-box');
                                chatBox.scrollTop = chatBox.scrollHeight;
                            } else if (data.done) {
                                console.log('景点讲解流式响应完成');
                                return;
                            } else if (data.error) {
                                contentDiv.innerHTML = `<div style="color: red;">❌ 讲解失败: ${data.error}</div>`;
                                return;
                            }
                        } catch (e) {
                            console.log('解析数据出错:', e);
                        }
                    }
                }
                
                readStream();
            });
        }
        
        readStream();
    })
    .catch(error => {
        console.error('景点讲解请求出错:', error);
        loadingMessage.remove();
        addMessage(`<div style="color: red;">❌ 景点讲解失败: ${error.message}</div>`, false);
    });
}

// 点击对话框外部关闭对话框
document.addEventListener('click', function(event) {
    const modal = document.getElementById('attractionGuideModal');
    if (event.target === modal) {
        closeAttractionGuideDialog();
    }
});

// 按ESC键关闭对话框
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('attractionGuideModal');
        if (modal.style.display === 'flex') {
            closeAttractionGuideDialog();
        }
    }
}); 