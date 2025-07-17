let isInitialLoad = true;

// 配置 marked.js 选项
marked.setOptions({
    breaks: true,  // 支持换行
    gfm: true,     // 启用 GitHub 风格的 Markdown
    headerIds: true, // 为标题添加 ID
    mangle: false,   // 不转义内联 HTML
    sanitize: false, // 不清理 HTML（由 DOMPurify 处理）
    smartLists: true, // 智能列表
    smartypants: true // 智能标点
});

document.addEventListener('DOMContentLoaded', function () {
     // 获取主要 DOM 元素
    const chatBox = document.getElementById('chat-box');               // 聊天消息容器
    const messageInput = document.getElementById('message-input');     // 输入框
    const sendBtn = document.getElementById('send-btn');               // 发送按钮
    const historyBtn = document.getElementById('history-btn');         // 历史记录按钮
    const historyModal = document.getElementById('history-modal');     // 历史记录弹窗
    const closeHistory = document.getElementById('close-history');     // 关闭弹窗（X）按钮
    const closeHistoryBtn = document.getElementById('close-history-btn'); // 关闭弹窗（底部）按钮
    const clearHistoryBtn = document.getElementById('clear-history');  // 清空历史按钮
    const historyList = document.getElementById('history-list');       // 历史记录列表容器
    const newChatBtn = document.getElementById('new-chat-btn');        // 新建对话按钮
    const email = document.querySelector('.user-info span')?.textContent; // 当前用户邮箱，用于加载和清空历史
    const searchToggleBtn = document.getElementById('search-toggle-btn'); // 搜索切换按钮
    // 搜索模式状态
    let isSearchMode = false;
    /** 滚动到底部 */
    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    /** 动态调整输入框高度（最多显示 5 行） */
    function adjustTextareaHeight() {
        const maxHeight = 5 * 24;
        messageInput.style.height = 'auto';
        const newHeight = Math.min(messageInput.scrollHeight, maxHeight);
        messageInput.style.height = newHeight + 'px';
    }
    
    messageInput.addEventListener('input', adjustTextareaHeight);
     /** 切换搜索模式 */
    function toggleSearchMode() {
        isSearchMode = !isSearchMode;
        searchToggleBtn.classList.toggle('active', isSearchMode);
        
        // 更新按钮提示文本
        if (isSearchMode) {
            searchToggleBtn.title = "已启用联网搜索模式，点击取消";
        } else {
            searchToggleBtn.title = "切换联网搜索模式";
        }
        
        console.log('搜索模式:', isSearchMode ? 'travel' : 'general');
    }

    searchToggleBtn.addEventListener('click', toggleSearchMode);
    
    /** 添加消息到聊天框 */
    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;

        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'bubble';

        if (isUser) {
            bubbleDiv.textContent = content;
        } else {
            const rawHtml = marked.parse(content);
            const cleanHtml = DOMPurify.sanitize(rawHtml);
            bubbleDiv.innerHTML = cleanHtml;
            // 立即应用代码高亮
            const codeBlocks = bubbleDiv.querySelectorAll('pre code');
            codeBlocks.forEach(block => {
                if (!block.className.includes('language-')) {
                    const preElement = block.closest('pre');
                    if (preElement && preElement.className.includes('language-')) {
                        block.className = preElement.className;
                    } else {
                        const codeContent = block.textContent || '';
                        if (codeContent.includes('def ') || codeContent.includes('import ') || codeContent.includes('print(')) {
                            block.className = 'language-python';
                        } else if (codeContent.includes('function ') || codeContent.includes('const ') || codeContent.includes('let ')) {
                            block.className = 'language-javascript';
                        } else {
                            block.className = 'language-javascript';
                        }
                    }
                }
                hljs.highlightElement(block);
            });
            const inlineCodes = bubbleDiv.querySelectorAll('code:not(pre code)');
            inlineCodes.forEach(code => {
                if (!code.className.includes('language-')) {
                    code.className = 'language-javascript';
                }
                hljs.highlightElement(code);
            });
            bubbleDiv.querySelectorAll('code').forEach(code => {
                if (!code.classList.contains('hljs')) {
                    hljs.highlightElement(code);
                }
            });
        }

        messageDiv.appendChild(bubbleDiv);
        chatBox.appendChild(messageDiv);
        const welcome = document.querySelector('.welcome-message');
        if (welcome) welcome.remove();
        scrollToBottom();
        return messageDiv;
    }

    /** 显示"加载中"动画（聊天中三点式） */
    function showLoading() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading-container';
        loadingDiv.innerHTML = `
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        `;
        chatBox.appendChild(loadingDiv);
        scrollToBottom();
    }

    /** 移除"加载中"动画 */
    function removeLoading() {
        const loadingDiv = document.querySelector('.loading-container');
        if (loadingDiv) loadingDiv.remove();
    }

    /** 发送消息至后端并处理返回 */
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message) return;
        
        // 如果是第一次发送消息，将输入框移到底部
        const inputWrapper = document.getElementById('input-wrapper');
        if (inputWrapper.classList.contains('centered')) {
            inputWrapper.classList.remove('centered');
            inputWrapper.classList.add('bottom');
        }
        
        // 禁用输入框和发送按钮，防止重复发送
        sendBtn.disabled = true;
        messageInput.disabled = true;

        addMessage(message, true);//显示用户消息
        showLoading();
        messageInput.value = '';
        adjustTextareaHeight();

        try {
            console.log('Sending message:', message); // 调试信息
            const res = await fetch('/send_message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: message,
                    agent_type: isSearchMode ? 'travel' : 'general'  
                })
            });

            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            removeLoading();
            
            // 创建AI消息容器，保持与历史记录一致的结构
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.className = 'message ai-message streaming';
            
            const bubbleDiv = document.createElement('div');
            bubbleDiv.className = 'bubble';
            
            aiMessageDiv.appendChild(bubbleDiv);
            chatBox.appendChild(aiMessageDiv);
            
            // 使用 EventSource 处理 SSE
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let chunkCount = 0; // 调试信息
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    console.log('Stream finished, total chunks:', chunkCount); // 调试信息
                    // 移除streaming类，确保与历史记录样式一致
                    aiMessageDiv.classList.remove('streaming');
                    bubbleDiv.removeAttribute('data-response-text');
                    break;
                }
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // 保留不完整的事件
                
                for (const line of lines) {
                    if (line.trim() === '') continue;
                    
                    const dataLine = line.split('\n').find(l => l.startsWith('data: '));
                    if (dataLine) {
                        try {
                            const data = JSON.parse(dataLine.slice(6));
                            console.log('Received SSE data:', data); // 调试信息
                            
                            if (data.error) {
                                console.error('Server error:', data.error); // 调试信息
                                bubbleDiv.innerHTML = `<div style="color: #e74c3c;">Error: ${data.error}</div>`;
                                break;
                            }
                            
                            if (data.chunk) {
                                chunkCount++; // 调试信息
                                console.log(`Chunk ${chunkCount}:`, data.chunk.substring(0, 50) + '...'); // 调试信息
                                
                                // 累积响应文本（类似旅行规划页面的方式）
                                let responseText = bubbleDiv.getAttribute('data-response-text') || '';
                                responseText += data.chunk;
                                bubbleDiv.setAttribute('data-response-text', responseText);
                                
                                // 重新解析完整的Markdown内容
                                const rawHtml = marked.parse(responseText);
                                const cleanHtml = DOMPurify.sanitize(rawHtml);
                                bubbleDiv.innerHTML = cleanHtml;
                                
                                // 立即应用代码高亮
                                const codeBlocks = bubbleDiv.querySelectorAll('pre code');
                                codeBlocks.forEach(block => {
                                    // 检查是否已经有语言类
                                    if (!block.className.includes('language-')) {
                                        // 尝试从父元素或兄弟元素中获取语言信息
                                        const preElement = block.closest('pre');
                                        if (preElement && preElement.className.includes('language-')) {
                                            block.className = preElement.className;
                                        } else {
                                            // 默认使用 javascript，但可以根据内容推断
                                            const codeContent = block.textContent || '';
                                            if (codeContent.includes('def ') || codeContent.includes('import ') || codeContent.includes('print(')) {
                                                block.className = 'language-python';
                                            } else if (codeContent.includes('function ') || codeContent.includes('const ') || codeContent.includes('let ')) {
                                                block.className = 'language-javascript';
                                            } else {
                                                block.className = 'language-javascript';
                                            }
                                        }
                                    }
                                    hljs.highlightElement(block);
                                });
                                
                                const inlineCodes = bubbleDiv.querySelectorAll('code:not(pre code)');
                                inlineCodes.forEach(code => {
                                    if (!code.className.includes('language-')) {
                                        code.className = 'language-javascript';
                                    }
                                    hljs.highlightElement(code);
                                });
                                
                                scrollToBottom();
                            }
                            
                            if (data.done) {
                                console.log('Stream completed'); // 调试信息
                                // 流式输出完成，移除光标效果和临时数据
                                aiMessageDiv.classList.remove('streaming');
                                bubbleDiv.removeAttribute('data-response-text');
                                break;
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e, dataLine);
                        }
                    }
                }
            }
            
            // 移除欢迎消息
            const welcome = document.querySelector('.welcome-message');
            if (welcome) welcome.remove();
            
        } catch (err) {
            console.error('Network error:', err); // 调试信息
            removeLoading();
            addMessage(`Network error: ${err.message}`);
        } finally {
            // 重新启用输入框和发送按钮
            sendBtn.disabled = false;
            messageInput.disabled = false;
            // 重新将焦点设置到输入框，方便用户继续输入
            messageInput.focus();
        }
    }

    // 回车键发送消息
    messageInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 发送按钮点击事件
    sendBtn.addEventListener('click', sendMessage);

    /** 删除特定对话 */
    function deleteConversation(convId, index) {
        if (!email) return;

        fetch('/delete_conversation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                email: email,
                conversation_id: convId 
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // 从DOM中移除该对话条目
                const historyEntries = document.querySelectorAll('.history-entry');
                if (historyEntries[index]) {
                    historyEntries[index].remove();
                }
                
                // 如果没有更多对话，显示空状态
                if (document.querySelectorAll('.history-entry').length === 0) {
                    historyList.innerHTML = '<div style="text-align:center; color:#999; padding:20px;">暂无历史记录</div>';
                }
                
                console.log('对话删除成功:', convId);
            } else {
                alert('删除失败：' + (data.error || '未知错误'));
            }
        })
        .catch(err => {
            console.error('删除对话失败:', err);
            alert('网络错误：' + err.message);
        });
    }

    /** 加载历史记录 */
    function loadHistory() {
        if (!email) return;

        historyList.innerHTML = '<div style="text-align:center; color:#999; padding:20px;">加载中...</div>';

        fetch('/load_history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        })
        .then(res => res.json())
        .then(data => {
            console.log('History data received:', data); // 调试信息
            
            if (data.error) {
                historyList.innerHTML = `<div style="text-align:center; color:#999; padding:20px;">${data.error}</div>`;
                return;
            }

            if (!data.history || data.history.length === 0) {
                historyList.innerHTML = '<div style="text-align:center; color:#999; padding:20px;">暂无历史记录</div>';
                return;
            }

            historyList.innerHTML = data.history.map((conv, idx) => `
                <div class="history-entry" data-index="${idx}" data-conv-id="${conv.id}" style="padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 10px; transition: background-color 0.2s; position: relative;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <div style="font-weight:bold; cursor: pointer;">对话 ${idx + 1} - ${conv.date}</div>
                        <button class="delete-conv-btn" style="background: #e74c3c; color: white; border: none; border-radius: 4px; padding: 4px 8px; font-size: 12px; cursor: pointer;" title="删除此对话">🗑️</button>
                    </div>
                    <div class="conv-content" style="line-height:1.6; max-height:100px; overflow-y:auto; font-size:0.9rem; cursor: pointer;">
                        ${conv.messages.slice(0, 2).map(msg => {
                            const text = msg.text || msg.content || '';
                            const isUser = msg.is_user || msg.isUser || false;
                            return `
                                <div style="margin-bottom:6px; padding:6px; border-radius:6px; ${isUser ? 'background-color:#e3f2fd;' : 'background-color:#f1f8e9;'}">
                                    ${isUser ? '你：' : '青鸾：'} ${text.substring(0, 100)}${text.length > 100 ? '...' : ''}
                                </div>
                            `;
                        }).join('')}
                        ${conv.messages.length > 2 ? `<div style="color:#666; font-size:0.85rem;">+ ${conv.messages.length - 2} 条消息...</div>` : ''}
                    </div>
                </div>
            `).join('');

            // 为删除按钮添加事件监听器
            document.querySelectorAll('.delete-conv-btn').forEach((btn, i) => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation(); // 阻止事件冒泡
                    const convId = data.history[i].id;
                    if (confirm(`确定要删除这个对话吗？此操作不可撤销。`)) {
                        deleteConversation(convId, i);
                    }
                });
            });

            // 为对话内容添加点击事件监听器
            document.querySelectorAll('.conv-content').forEach((content, i) => {
                content.addEventListener('click', () => {
                    console.log('History entry clicked:', i); // 调试信息
                    const selected = data.history[i];
                    console.log('Selected conversation:', selected); // 调试信息
                    
                    chatBox.innerHTML = '';
                    selected.messages.forEach(msg => {
                        console.log('Processing message:', msg); // 调试信息
                        // 确保字段名正确
                        const text = msg.text || msg.content || '';
                        const isUser = msg.is_user || msg.isUser || false;
                        addMessage(text, isUser);
                    });
                    
                    // 加载历史对话后，确保输入框在底部
                    const inputWrapper = document.getElementById('input-wrapper');
                    inputWrapper.classList.remove('centered');
                    inputWrapper.classList.add('bottom');
                    
                    historyModal.style.display = 'none';
                    
                    // 加载历史对话后，将焦点设置到输入框
                    messageInput.focus();
                    
                    // 确保历史记录中的代码也能正确高亮
                    const codeBlocks = chatBox.querySelectorAll('pre code');
                    codeBlocks.forEach(block => {
                        if (!block.className.includes('language-')) {
                            block.className = 'language-javascript';
                        }
                        hljs.highlightElement(block);
                    });
                    
                    const inlineCodes = chatBox.querySelectorAll('code:not(pre code)');
                    inlineCodes.forEach(code => {
                        if (!code.className.includes('language-')) {
                            code.className = 'language-javascript';
                        }
                        hljs.highlightElement(code);
                    });
                    
                    // 确保所有代码元素都被正确高亮
                    chatBox.querySelectorAll('code').forEach(code => {
                        if (!code.classList.contains('hljs')) {
                            hljs.highlightElement(code);
                        }
                    });
                });
            });
        })
        .catch(err => {
            historyList.innerHTML = `<div style="text-align:center; color:#e74c3c; padding:20px;">加载失败：${err.message}</div>`;
        });
    }

    /** 初始化聊天界面 */
    function initChat() {
        chatBox.innerHTML = '';

        const welcome = document.createElement('div');
        welcome.className = 'welcome-message';
        welcome.innerHTML = '<p>欢迎来到青鸾向导！<br>我是您的智能助手，无论是出行安排，还是问题解答，都随时为您服务。<br><span style="color: #667eea; font-weight: 600;">有什么可以帮助您的吗？</span></p>';
        chatBox.appendChild(welcome);

        // 重置输入框到中间位置
        const inputWrapper = document.getElementById('input-wrapper');
        inputWrapper.classList.remove('bottom');
        inputWrapper.classList.add('centered');
        
        // 初始化时将焦点设置到输入框
        messageInput.focus();
        
        scrollToBottom();
    }

    /** 历史记录相关事件绑定 */
    if (historyBtn) {
        historyBtn.addEventListener('click', () => {
            historyModal.style.display = 'flex';
            loadHistory();
        });
    }

    if (closeHistory) {
        closeHistory.addEventListener('click', () => {
            historyModal.style.display = 'none';
            // 关闭历史记录弹窗后，将焦点设置到输入框
            messageInput.focus();
        });
    }

    if (closeHistoryBtn) {
        closeHistoryBtn.addEventListener('click', () => {
            historyModal.style.display = 'none';
            // 关闭历史记录弹窗后，将焦点设置到输入框
            messageInput.focus();
        });
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', () => {
            if (!email || !confirm('确定要清除所有历史记录吗？此操作不可撤销。')) return;

            fetch('/clear_history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    alert('历史记录已清除');
                    historyList.innerHTML = '<div style="text-align:center; color:#999; padding:20px;">历史记录已清空</div>';
                } else {
                    alert('清除失败：' + data.error);
                }
            })
            .catch(err => alert('网络错误：' + err.message));
        });
    }

    /** 新建对话：清空聊天界面并通知服务器 */
    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            fetch('/new_conversation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(() => {
                initChat();
            })
            .catch(err => console.error('Error creating new conversation:', err));
        });
    }

    /** 页面初次加载初始化聊天界面 */
    initChat();
    // 初始化时滚动到底
    scrollToBottom();
    
    // 检查是否有历史消息，如果有则确保输入框在底部
    setTimeout(() => {
        const messages = chatBox.querySelectorAll('.message');
        if (messages.length > 0) {
            const inputWrapper = document.getElementById('input-wrapper');
            inputWrapper.classList.remove('centered');
            inputWrapper.classList.add('bottom');
        }
        // 页面加载完成后确保输入框获得焦点
        messageInput.focus();
    }, 100);
});
