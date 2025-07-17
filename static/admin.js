// 当前搜索状态
let currentSearch = {
    users: { query: '', page: 1 },
    conversations: { query: '', page: 1 },
    messages: { query: '', page: 1 }
};

// 当前管理员管理状态
let currentAdminPage = 1;
let currentLogPage = 1;

let currentPage = 1;
const itemsPerPage = 10;

// 初始化页面
document.addEventListener('DOMContentLoaded', function() {
    // 绑定菜单点击事件
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function() {
            const section = this.getAttribute('data-section');
            showSection(section);
            
            // 更新菜单激活状态
            document.querySelectorAll('.menu-item').forEach(i => {
                i.classList.remove('active');
            });
            this.classList.add('active');
        });
    });
    
    // 加载仪表盘数据
    loadDashboardData();
    
    // 加载用户数据
    loadUsersData();
    
    // 管理员搜索
    document.getElementById('admin-search').addEventListener('input', function(e) {
        const query = this.value.trim();
        // 实现搜索功能
    });
    
    // 日志搜索
    document.getElementById('log-search').addEventListener('input', function(e) {
        const query = this.value.trim();
        // 实现搜索功能
    });
    
    // // 绑定搜索事件
    // document.getElementById('user-search').addEventListener('keyup', function(e) {
    //     if (e.key === 'Enter') {
    //         searchUsers(this.value);
    //     }
    // });
    
    // document.getElementById('conversation-search').addEventListener('keyup', function(e) {
    //     if (e.key === 'Enter') {
    //         searchConversations(this.value);
    //     }
    // });
    
    // document.getElementById('message-search').addEventListener('keyup', function(e) {
    //     if (e.key === 'Enter') {
    //         searchMessages(this.value);
    //     }
    // });
});

// 显示指定内容区域
function showSection(section) {
    // 隐藏所有内容区域
    document.querySelectorAll('.content-section').forEach(el => {
        el.classList.remove('active');
    });
    
    // 显示选中的内容区域
    const sectionEl = document.getElementById(`${section}-section`);
    if (sectionEl) {
        sectionEl.classList.add('active');
        
        // 如果需要，加载数据
        if (section === 'dashboard') {
            loadDashboardData();
        } else if (section === 'users') {
            loadUsersData();
        } else if (section === 'conversations') {
            loadConversationsData();
        } else if (section === 'messages') {
            loadMessagesData();
        }
    }

    if (section === 'admins') {
        loadAdminsData(currentAdminPage);
    } else if (section === 'admin-logs') {
        loadAdminLogs(currentLogPage);
    }
}

// 显示用户详情
function showUserDetail(email) {
    // 显示加载状态
    document.getElementById('user-conversations-table').innerHTML = 
        '<tr><td colspan="4" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    // 获取用户详情
    fetch(`/admin/user/${encodeURIComponent(email)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('user-detail-section', data.error);
                return;
            }
            
            // 设置用户详情
            document.getElementById('user-detail-name').textContent = '用户详情';
            document.getElementById('user-detail-email').textContent = email;
            document.getElementById('user-avatar').textContent = email.charAt(0).toUpperCase();
            document.getElementById('user-full-email').textContent = email;
            document.getElementById('user-reg-time').textContent = formatDateTime(data.user.created_at);
            document.getElementById('user-last-login').textContent = data.user.last_login ? formatDateTime(data.user.last_login) : '从未登录';
            document.getElementById('user-conv-count').textContent = data.stats.conv_count;
            document.getElementById('user-msg-count').textContent = data.stats.msg_count;
            document.getElementById('user-avg-msg').textContent = data.stats.avg_msg_per_conv.toFixed(1);
            
            // 渲染用户会话
            const userConversationsTable = document.getElementById('user-conversations-table');
            userConversationsTable.innerHTML = '';
            
            if (data.conversations.length === 0) {
                userConversationsTable.innerHTML = '<tr><td colspan="4">暂无会话记录</td></tr>';
                return;
            }
            
            data.conversations.forEach(conv => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${conv.id}</td>
                    <td>${conv.date}</td>
                    <td>${formatDateTime(conv.created_at)}</td>
                    <td>
                        <button class="action-btn" title="查看详情" onclick="showConversationDetail('${conv.id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                `;
                userConversationsTable.appendChild(row);
            });
            
            // 显示用户详情区域
            showSection('user-detail');
        })
        .catch(error => {
            showError('user-detail-section', '加载用户详情失败: ' + error.message);
        });
}

// 加载仪表盘数据
function loadDashboardData() {
    // 显示加载状态
    document.getElementById('recent-users').innerHTML = 
        '<tr><td colspan="3" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    // 隐藏错误消息
    document.getElementById('dashboard-error').style.display = 'none';
    
    // 获取仪表盘数据
    fetch('/admin/stats')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('dashboard-section', data.error);
                return;
            }
            
            // 更新统计数据
            document.getElementById('total-users').textContent = data.total_users;
            document.getElementById('active-users').textContent = data.active_users;
            document.getElementById('total-conversations').textContent = data.total_conversations;
            document.getElementById('total-messages').textContent = data.total_messages;
            
            // 加载最近用户
            const recentUsersBody = document.getElementById('recent-users');
            recentUsersBody.innerHTML = '';
            
            if (data.recent_users.length === 0) {
                recentUsersBody.innerHTML = '<tr><td colspan="3">暂无用户活动</td></tr>';
                return;
            }
            
            data.recent_users.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.email}</td>
                    <td>${user.last_login ? formatDateTime(user.last_login) : '从未登录'}</td>
                    <td><span class="status active">活跃</span></td>
                `;
                recentUsersBody.appendChild(row);
            });
        })
        .catch(error => {
            showError('dashboard-section', '加载仪表盘数据失败: ' + error.message);
        });
}

// // 加载用户数据
// function loadUsersData(page = 1) {
//     const usersBody = document.getElementById('users-table-body');
//     const pagination = document.getElementById('users-pagination');
    
//     usersBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     fetch(`/admin/users?page=${page}&per_page=${itemsPerPage}`)
//         .then(response => response.json())
//         .then(data => {
//             if (data.error) {
//                 showError('users-section', data.error);
//                 return;
//             }
            
//             usersBody.innerHTML = '';
            
//             if (data.users.length === 0) {
//                 usersBody.innerHTML = '<tr><td colspan="5">暂无用户数据</td></tr>';
//                 return;
//             }
            
//             data.users.forEach(user => {
//                 const row = document.createElement('tr');
//                 row.innerHTML = `
//                     <td>${user.id}</td>
//                     <td>${user.email}</td>
//                     <td>${formatDateTime(user.created_at)}</td>
//                     <td>${user.last_login ? formatDateTime(user.last_login) : '从未登录'}</td>
//                     <td>
//                         <button class="action-btn" title="查看详情" onclick="showUserDetail('${user.email}')">
//                             <i class="fas fa-eye"></i>
//                         </button>
//                     </td>
//                 `;
//                 usersBody.appendChild(row);
//             });
            
//             // 更新分页控件
//             updatePagination(pagination, data.total, page, 'users');
            
//             // 更新当前页面
//             currentPage.users = page;
//         })
//         .catch(error => {
//             showError('users-section', '加载用户数据失败: ' + error.message);
//         });
// }

// // 加载会话数据
// function loadConversationsData(page = 1) {
//     const conversationsBody = document.getElementById('conversations-table-body');
//     const pagination = document.getElementById('conversations-pagination');
    
//     conversationsBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     fetch(`/admin/conversations?page=${page}&per_page=${itemsPerPage}`)
//         .then(response => response.json())
//         .then(data => {
//             if (data.error) {
//                 showError('conversations-section', data.error);
//                 return;
//             }
            
//             conversationsBody.innerHTML = '';
            
//             if (data.conversations.length === 0) {
//                 conversationsBody.innerHTML = '<tr><td colspan="5">暂无会话数据</td></tr>';
//                 return;
//             }
            
//             data.conversations.forEach(conv => {
//                 const row = document.createElement('tr');
//                 row.innerHTML = `
//                     <td>${conv.id}</td>
//                     <td>${conv.user_email}</td>
//                     <td>${conv.date}</td>
//                     <td>${conv.message_count}</td>
//                     <td>
//                         <button class="action-btn" title="查看详情">
//                             <i class="fas fa-eye"></i>
//                         </button>
//                     </td>
//                 `;
//                 conversationsBody.appendChild(row);
//             });
            
//             // 更新分页控件
//             updatePagination(pagination, data.total, page, 'conversations');
            
//             // 更新当前页面
//             currentPage.conversations = page;
//         })
//         .catch(error => {
//             showError('conversations-section', '加载会话数据失败: ' + error.message);
//         });
// }

// // 加载消息数据
// function loadMessagesData(page = 1) {
//     const messagesBody = document.getElementById('messages-table-body');
//     const pagination = document.getElementById('messages-pagination');
    
//     messagesBody.innerHTML = '<tr><td colspan="6" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     fetch(`/admin/messages?page=${page}&per_page=${itemsPerPage}`)
//         .then(response => response.json())
//         .then(data => {
//             if (data.error) {
//                 showError('messages-section', data.error);
//                 return;
//             }
            
//             messagesBody.innerHTML = '';
            
//             if (data.messages.length === 0) {
//                 messagesBody.innerHTML = '<tr><td colspan="6">暂无消息数据</td></tr>';
//                 return;
//             }
            
//             data.messages.forEach(msg => {
//                 // 截断长消息
//                 const content = msg.text.length > 50 ? 
//                     msg.text.substring(0, 47) + '...' : msg.text;
                
//                 const row = document.createElement('tr');
//                 row.innerHTML = `
//                     <td>${msg.id}</td>
//                     <td>${msg.user_email}</td>
//                     <td>${msg.conversation_id}</td>
//                     <td>${content}</td>
//                     <td>${formatDateTime(msg.created_at)}</td>
//                     <td>${msg.is_user ? '用户' : '系统'} (${msg.agent_type})</td>
//                 `;
//                 messagesBody.appendChild(row);
//             });
            
//             // 更新分页控件
//             updatePagination(pagination, data.total, page, 'messages');
            
//             // 更新当前页面
//             currentPage.messages = page;
//         })
//         .catch(error => {
//             showError('messages-section', '加载消息数据失败: ' + error.message);
//         });
// }

// // 搜索用户
// function searchUsers(query) {
//     // 简化实现 - 实际应用中应使用后端搜索API
//     const usersBody = document.getElementById('users-table-body');
//     usersBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     // 模拟搜索延迟
//     setTimeout(() => {
//         loadUsersData();
//     }, 500);
// }

// // 搜索会话
// function searchConversations(query) {
//     // 简化实现
//     const conversationsBody = document.getElementById('conversations-table-body');
//     conversationsBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     setTimeout(() => {
//         loadConversationsData();
//     }, 500);
// }

// // 搜索消息
// function searchMessages(query) {
//     // 简化实现
//     const messagesBody = document.getElementById('messages-table-body');
//     messagesBody.innerHTML = '<tr><td colspan="6" class="loading"><div class="loading-spinner"></div></td></tr>';
    
//     setTimeout(() => {
//         loadMessagesData();
//     }, 500);
// }

// 更新分页控件
function updatePagination(element, totalItems, currentPage, type) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    element.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    // 添加上一页按钮
    const prevButton = document.createElement('div');
    prevButton.className = 'page-item';
    prevButton.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevButton.addEventListener('click', () => {
        if (currentPage > 1) {
            switch(type) {
                case 'users':
                    loadUsersData(currentPage - 1);
                    break;
                case 'conversations':
                    loadConversationsData(currentPage - 1);
                    break;
                case 'messages':
                    loadMessagesData(currentPage - 1);
                    break;
            }
        }
    });
    element.appendChild(prevButton);
    
    // 添加页码按钮
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('div');
        pageButton.className = 'page-item';
        if (i === currentPage) pageButton.classList.add('active');
        pageButton.textContent = i;
        pageButton.addEventListener('click', () => {
            switch(type) {
                case 'users':
                    loadUsersData(i);
                    break;
                case 'conversations':
                    loadConversationsData(i);
                    break;
                case 'messages':
                    loadMessagesData(i);
                    break;
            }
        });
        element.appendChild(pageButton);
    }
    
    // 添加下一页按钮
    const nextButton = document.createElement('div');
    nextButton.className = 'page-item';
    nextButton.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextButton.addEventListener('click', () => {
        if (currentPage < totalPages) {
            switch(type) {
                case 'users':
                    loadUsersData(currentPage + 1);
                    break;
                case 'conversations':
                    loadConversationsData(currentPage + 1);
                    break;
                case 'messages':
                    loadMessagesData(currentPage + 1);
                    break;
            }
        }
    });
    element.appendChild(nextButton);
}

// 格式化日期时间
function formatDateTime(datetimeStr) {
    if (!datetimeStr) return '';
    const date = new Date(datetimeStr);
    return date.toLocaleString('zh-CN');
}

// 显示错误消息
function showError(section, message) {
    const errorElement = document.getElementById(`${section}-error`);
    if (!errorElement) return;
    
    const errorText = errorElement.querySelector('span');
    if (errorText) {
        errorText.textContent = message;
    }
    errorElement.style.display = 'flex';
}

// 新增：显示会话详情
function showConversationDetail(convId) {
    // 显示加载状态
    document.getElementById('conversation-messages').innerHTML = 
        '<div class="loading"><div class="loading-spinner"></div></div>';
    
    // 获取会话详情
    fetch(`/admin/conversation/${convId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('conversation-detail-section', data.error);
                return;
            }
            
            const conv = data.conversation;
            const messages = data.messages;
            
            // 设置会话基本信息
            document.getElementById('detail-conv-id').textContent = conv.id;
            document.getElementById('detail-user-email').textContent = conv.user_email;
            document.getElementById('detail-created-at').textContent = formatDateTime(conv.created_at);
            document.getElementById('detail-message-count').textContent = conv.message_count;
            
            // 渲染消息列表
            const messagesContainer = document.getElementById('conversation-messages');
            messagesContainer.innerHTML = '';
            
            if (messages.length === 0) {
                messagesContainer.innerHTML = '<p>此会话没有消息</p>';
                return;
            }
            
            messages.forEach(msg => {
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message-item';
                messageDiv.innerHTML = `
                    <div class="message-header">
                        <div class="${msg.is_user ? 'message-user' : 'message-system'}">
                            ${msg.is_user ? '用户' : '系统'} (${msg.agent_type})
                        </div>
                        <div class="message-time">${formatDateTime(msg.created_at)}</div>
                        <button class="action-btn" title="删除消息" onclick="deleteMessage(${msg.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                    <div class="message-content">${msg.text}</div>
                `;
                messagesContainer.appendChild(messageDiv);
            });
            
            // 显示会话详情区域
            showSection('conversation-detail');
        })
        .catch(error => {
            showError('conversation-detail-section', '加载会话详情失败: ' + error.message);
        });
}

// 修改：用户列表加载函数
function loadUsersData(page = 1) {
    const usersBody = document.getElementById('users-table-body');
    const pagination = document.getElementById('users-pagination');
    
    usersBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    fetch(`/admin/users?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('users-section', data.error);
                return;
            }
            
            usersBody.innerHTML = '';
            
            if (data.users.length === 0) {
                usersBody.innerHTML = '<tr><td colspan="5">暂无用户数据</td></tr>';
                return;
            }
            
            data.users.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.id}</td>
                    <td>${user.email}</td>
                    <td>${formatDateTime(user.created_at)}</td>
                    <td>${user.last_login ? formatDateTime(user.last_login) : '从未登录'}</td>
                    <td>
                        <button class="action-btn" title="查看详情" onclick="showUserDetail('${user.email}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn" title="删除用户" onclick="deleteUser('${user.email}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                usersBody.appendChild(row);
            });
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, 'users');
            
            // 更新当前页面
            currentPage.users = page;
        })
        .catch(error => {
            showError('users-section', '加载用户数据失败: ' + error.message);
        });
}

// 修改：会话列表加载函数
function loadConversationsData(page = 1) {
    const conversationsBody = document.getElementById('conversations-table-body');
    const pagination = document.getElementById('conversations-pagination');
    
    conversationsBody.innerHTML = '<tr><td colspan="5" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    fetch(`/admin/conversations?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('conversations-section', data.error);
                return;
            }
            
            conversationsBody.innerHTML = '';
            
            if (data.conversations.length === 0) {
                conversationsBody.innerHTML = '<tr><td colspan="5">暂无会话数据</td></tr>';
                return;
            }
            
            data.conversations.forEach(conv => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${conv.id}</td>
                    <td>${conv.user_email}</td>
                    <td>${conv.date}</td>
                    <td>${conv.message_count}</td>
                    <td>
                        <button class="action-btn" title="查看详情" onclick="showConversationDetail('${conv.id}')">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="action-btn" title="删除会话" onclick="deleteConversation('${conv.id}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                conversationsBody.appendChild(row);
            });
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, 'conversations');
            
            // 更新当前页面
            currentPage.conversations = page;
        })
        .catch(error => {
            showError('conversations-section', '加载会话数据失败: ' + error.message);
        });
}

// 修改：消息列表加载函数
function loadMessagesData(page = 1) {
    const messagesBody = document.getElementById('messages-table-body');
    const pagination = document.getElementById('messages-pagination');
    
    messagesBody.innerHTML = '<tr><td colspan="7" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    fetch(`/admin/messages?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('messages-section', data.error);
                return;
            }
            
            messagesBody.innerHTML = '';
            
            if (data.messages.length === 0) {
                messagesBody.innerHTML = '<tr><td colspan="7">暂无消息数据</td></tr>';
                return;
            }
            
            data.messages.forEach(msg => {
                // 截断长消息
                const content = msg.text.length > 50 ? 
                    msg.text.substring(0, 47) + '...' : msg.text;
                
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${msg.id}</td>
                    <td>${msg.user_email}</td>
                    <td>${msg.conversation_id}</td>
                    <td>${content}</td>
                    <td>${formatDateTime(msg.created_at)}</td>
                    <td>${msg.is_user ? '用户' : '系统'} (${msg.agent_type})</td>
                    <td>
                        <button class="action-btn" title="删除消息" onclick="deleteMessage(${msg.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                messagesBody.appendChild(row);
            });
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, 'messages');
            
            // 更新当前页面
            currentPage.messages = page;
        })
        .catch(error => {
            showError('messages-section', '加载消息数据失败: ' + error.message);
        });
}

// 新增：删除用户函数
function deleteUser(email) {
    if (confirm(`确定要永久删除用户 ${email} 及其所有数据吗？此操作不可撤销！`)) {
        fetch(`/admin/user/${encodeURIComponent(email)}/delete`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('用户删除成功');
                loadUsersData(currentPage.users);
                showSection('users');
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
}

// 新增：删除会话函数
function deleteConversation(convId) {
    if (confirm(`确定要永久删除会话 ${convId} 及其所有消息吗？此操作不可撤销！`)) {
        fetch(`/admin/conversation/${convId}/delete`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('会话删除成功');
                
                // 如果当前在会话详情页，返回会话列表
                if (document.getElementById('conversation-detail-section').classList.contains('active')) {
                    showSection('conversations');
                }
                
                loadConversationsData(currentPage.conversations);
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
}

// 新增：删除消息函数
function deleteMessage(messageId) {
    if (confirm('确定要永久删除这条消息吗？此操作不可撤销！')) {
        fetch(`/admin/message/${messageId}/delete`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('消息删除成功');
                
                // 如果当前在会话详情页，刷新会话
                if (document.getElementById('conversation-detail-section').classList.contains('active')) {
                    const convId = document.getElementById('detail-conv-id').textContent;
                    showConversationDetail(convId);
                } else {
                    loadMessagesData(currentPage.messages);
                }
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
}


// 初始化搜索框
document.addEventListener('DOMContentLoaded', function() {
    // 绑定搜索事件
    document.getElementById('user-search').addEventListener('input', function(e) {
        const query = this.value.trim();
        currentSearch.users.query = query;
        if (query.length >= 2 || query.length === 0) {
            debouncedSearch('users', query);
        }
    });
    
    document.getElementById('conversation-search').addEventListener('input', function(e) {
        const query = this.value.trim();
        currentSearch.conversations.query = query;
        if (query.length >= 2 || query.length === 0) {
            debouncedSearch('conversations', query);
        }
    });
    
    document.getElementById('message-search').addEventListener('input', function(e) {
        const query = this.value.trim();
        currentSearch.messages.query = query;
        if (query.length >= 2 || query.length === 0) {
            debouncedSearch('messages', query);
        }
    });
    
    // 添加搜索提示
    addSearchTips();
});

// 添加搜索提示
function addSearchTips() {
    const userSearch = document.getElementById('user-search');
    userSearch.placeholder = "搜索用户（按邮箱）...";
    
    const convSearch = document.getElementById('conversation-search');
    convSearch.placeholder = "搜索会话（按ID或用户邮箱）...";
    
    const msgSearch = document.getElementById('message-search');
    msgSearch.placeholder = "搜索消息（按内容、用户邮箱或会话ID）...";
}

// 防抖函数（减少API请求）
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 搜索函数（带防抖）
const debouncedSearch = debounce((type, query) => {
    searchData(type, query);
}, 500);

// 执行搜索
function searchData(type, query) {
    const section = `${type}-section`;
    
    // 显示加载状态
    const tableBody = document.getElementById(`${type}-table-body`);
    const pagination = document.getElementById(`${type}-pagination`);
    tableBody.innerHTML = '<tr><td colspan="7" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    // 获取当前页码
    const page = currentSearch[type].page;
    
    // 执行搜索
    fetch(`/admin/search?type=${type}&query=${encodeURIComponent(query)}&page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(section, data.error);
                return;
            }
            
            // 更新表格
            renderTable(type, data);
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, type, data.query);
            
            // 显示搜索结果计数
            showSearchCount(type, data.total, data.query);
        })
        .catch(error => {
            showError(section, '搜索失败: ' + error.message);
        });
}

// 渲染表格数据
function renderTable(type, data) {
    const tableBody = document.getElementById(`${type}-table-body`);
    tableBody.innerHTML = '';
    
    if (data[type].length === 0) {
        const noResults = currentSearch[type].query ? 
            `<tr><td colspan="7">没有找到匹配的${getTypeName(type)}</td></tr>` :
            `<tr><td colspan="7">暂无${getTypeName(type)}数据</td></tr>`;
        tableBody.innerHTML = noResults;
        return;
    }
    
    // 用户表格
    if (type === 'users') {
        data.users.forEach(user => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${user.id}</td>
                <td>${highlightMatch(user.email, currentSearch.users.query)}</td>
                <td>${formatDateTime(user.created_at)}</td>
                <td>${user.last_login ? formatDateTime(user.last_login) : '从未登录'}</td>
                <td>
                    <button class="action-btn" title="查看详情" onclick="showUserDetail('${user.email}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn" title="删除用户" onclick="deleteUser('${user.email}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
    // 会话表格
    else if (type === 'conversations') {
        data.conversations.forEach(conv => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${highlightMatch(conv.id, currentSearch.conversations.query)}</td>
                <td>${highlightMatch(conv.user_email, currentSearch.conversations.query)}</td>
                <td>${conv.date}</td>
                <td>${conv.message_count}</td>
                <td>
                    <button class="action-btn" title="查看详情" onclick="showConversationDetail('${conv.id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn" title="删除会话" onclick="deleteConversation('${conv.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
    // 消息表格
    else if (type === 'messages') {
        data.messages.forEach(msg => {
            // 高亮匹配内容
            const content = msg.text.length > 100 ? 
                msg.text.substring(0, 97) + '...' : msg.text;
            
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${msg.id}</td>
                <td>${highlightMatch(msg.user_email, currentSearch.messages.query)}</td>
                <td>${highlightMatch(msg.conversation_id, currentSearch.messages.query)}</td>
                <td>${highlightMatch(content, currentSearch.messages.query)}</td>
                <td>${formatDateTime(msg.created_at)}</td>
                <td>${msg.is_user ? '用户' : '系统'} (${msg.agent_type})</td>
                <td>
                    <button class="action-btn" title="删除消息" onclick="deleteMessage(${msg.id})">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
}

// 显示搜索结果计数
function showSearchCount(type, total, query) {
    const countElement = document.getElementById(`${type}-search-count`);
    if (!countElement) return;
    
    if (query) {
        countElement.innerHTML = `找到 <span class="highlight">${total}</span> 个匹配 "${query}" 的结果`;
        countElement.style.display = 'block';
    } else {
        countElement.style.display = 'none';
    }
}

// 高亮匹配文本
function highlightMatch(text, query) {
    if (!query || !text) return text;
    
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// 转义正则特殊字符
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 获取类型名称
function getTypeName(type) {
    const names = {
        'users': '用户',
        'conversations': '会话',
        'messages': '消息'
    };
    return names[type] || '项目';
}

// 更新分页控件（支持搜索）
function updatePagination(element, totalItems, currentPage, type, query = '') {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    element.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    // 添加上一页按钮
    const prevButton = document.createElement('div');
    prevButton.className = 'page-item';
    prevButton.innerHTML = '<i class="fas fa-chevron-left"></i>';
    prevButton.addEventListener('click', () => {
        if (currentPage > 1) {
            currentSearch[type].page = currentPage - 1;
            if (query) {
                searchData(type, query);
            } else {
                switch(type) {
                    case 'users': loadUsersData(currentSearch[type].page); break;
                    case 'conversations': loadConversationsData(currentSearch[type].page); break;
                    case 'messages': loadMessagesData(currentSearch[type].page); break;
                }
            }
        }
    });
    element.appendChild(prevButton);
    
    // 添加页码按钮
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('div');
        pageButton.className = 'page-item';
        if (i === currentPage) pageButton.classList.add('active');
        pageButton.textContent = i;
        pageButton.addEventListener('click', () => {
            currentSearch[type].page = i;
            if (query) {
                searchData(type, query);
            } else {
                switch(type) {
                    case 'users': loadUsersData(i); break;
                    case 'conversations': loadConversationsData(i); break;
                    case 'messages': loadMessagesData(i); break;
                }
            }
        });
        element.appendChild(pageButton);
    }
    
    // 添加下一页按钮
    const nextButton = document.createElement('div');
    nextButton.className = 'page-item';
    nextButton.innerHTML = '<i class="fas fa-chevron-right"></i>';
    nextButton.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentSearch[type].page = currentPage + 1;
            if (query) {
                searchData(type, query);
            } else {
                switch(type) {
                    case 'users': loadUsersData(currentSearch[type].page); break;
                    case 'conversations': loadConversationsData(currentSearch[type].page); break;
                    case 'messages': loadMessagesData(currentSearch[type].page); break;
                }
            }
        }
    });
    element.appendChild(nextButton);
}


// 加载管理员数据
function loadAdminsData(page = 1) {
    const adminsBody = document.getElementById('admins-table-body');
    const pagination = document.getElementById('admins-pagination');
    
    adminsBody.innerHTML = '<tr><td colspan="7" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    fetch(`/admin/admins?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('admins-section', data.error);
                return;
            }
            
            adminsBody.innerHTML = '';
            
            if (data.admins.length === 0) {
                adminsBody.innerHTML = '<tr><td colspan="7">暂无管理员数据</td></tr>';
                return;
            }
            
            data.admins.forEach(admin => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${admin.id}</td>
                    <td>${admin.username}</td>
                    <td>${admin.email || '未设置'}</td>
                    <td><span class="role-tag role-${admin.role}">${admin.role === 'superadmin' ? '超级管理员' : '管理员'}</span></td>
                    <td>${formatDateTime(admin.created_at)}</td>
                    <td>${admin.last_login ? formatDateTime(admin.last_login) : '从未登录'}</td>
                    <td>
                        <button class="action-btn" title="编辑" onclick="showEditAdminModal(${admin.id}, '${admin.username}', '${admin.email || ''}', '${admin.role}')">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="action-btn" title="删除" onclick="deleteAdmin(${admin.id}, '${admin.username}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                adminsBody.appendChild(row);
            });
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, 'admins');
            
            // 更新当前页面
            currentAdminPage = page;
        })
        .catch(error => {
            showError('admins-section', '加载管理员数据失败: ' + error.message);
        });
}

// 加载操作日志
function loadAdminLogs(page = 1) {
    const logsBody = document.getElementById('logs-table-body');
    const pagination = document.getElementById('logs-pagination');
    
    logsBody.innerHTML = '<tr><td colspan="6" class="loading"><div class="loading-spinner"></div></td></tr>';
    
    fetch(`/admin/logs?page=${page}&per_page=${itemsPerPage}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError('admin-logs-section', data.error);
                return;
            }
            
            logsBody.innerHTML = '';
            
            if (data.logs.length === 0) {
                logsBody.innerHTML = '<tr><td colspan="6">暂无操作日志</td></tr>';
                return;
            }
            
            data.logs.forEach(log => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${log.id}</td>
                    <td>${log.admin_username}</td>
                    <td>${log.action}</td>
                    <td>${log.target_id ? log.target_id : '无'}</td>
                    <td>${log.details || '无'}</td>
                    <td>${formatDateTime(log.created_at)}</td>
                `;
                logsBody.appendChild(row);
            });
            
            // 更新分页控件
            updatePagination(pagination, data.total, page, 'logs');
            
            // 更新当前页面
            currentLogPage = page;
        })
        .catch(error => {
            showError('admin-logs-section', '加载操作日志失败: ' + error.message);
        });
}

// 显示添加管理员模态框
function showAddAdminModal() {
    document.getElementById('admin-username').value = '';
    document.getElementById('admin-password').value = '';
    document.getElementById('admin-password-confirm').value = '';
    document.getElementById('admin-email').value = '';
    document.getElementById('admin-role').value = 'admin';
    
    document.getElementById('add-admin-modal').classList.add('active');
}

// 显示编辑管理员模态框
function showEditAdminModal(adminId, username, email, role) {
    document.getElementById('edit-admin-id').value = adminId;
    document.getElementById('edit-admin-username').value = username;
    document.getElementById('edit-admin-email').value = email || '';
    document.getElementById('edit-admin-role').value = role;
    document.getElementById('edit-admin-password').value = '';
    document.getElementById('edit-admin-password-confirm').value = '';
    
    document.getElementById('edit-admin-modal').classList.add('active');
}

// 关闭模态框
function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// 添加管理员
document.getElementById('add-admin-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const username = document.getElementById('admin-username').value.trim();
    const password = document.getElementById('admin-password').value;
    const passwordConfirm = document.getElementById('admin-password-confirm').value;
    const email = document.getElementById('admin-email').value.trim();
    const role = document.getElementById('admin-role').value;
    
    if (!username) {
        alert('用户名不能为空');
        return;
    }
    
    if (!password) {
        alert('密码不能为空');
        return;
    }
    
    if (password !== passwordConfirm) {
        alert('两次输入的密码不一致');
        return;
    }
    
    fetch('/admin/admin/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username,
            password,
            email,
            role
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('管理员添加成功');
            closeModal('add-admin-modal');
            loadAdminsData(currentAdminPage);
        } else {
            alert('添加失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        alert('添加失败: ' + error.message);
    });
});

// 编辑管理员
document.getElementById('edit-admin-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const adminId = document.getElementById('edit-admin-id').value;
    const email = document.getElementById('edit-admin-email').value.trim();
    const role = document.getElementById('edit-admin-role').value;
    const password = document.getElementById('edit-admin-password').value;
    const passwordConfirm = document.getElementById('edit-admin-password-confirm').value;
    
    if (password && password !== passwordConfirm) {
        alert('两次输入的密码不一致');
        return;
    }
    
    fetch(`/admin/admin/${adminId}/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            email,
            role,
            password: password || null
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('管理员信息更新成功');
            closeModal('edit-admin-modal');
            loadAdminsData(currentAdminPage);
        } else {
            alert('更新失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        alert('更新失败: ' + error.message);
    });
});

// 删除管理员
function deleteAdmin(adminId, username) {
    if (confirm(`确定要永久删除管理员 "${username}" 吗？此操作不可撤销！`)) {
        fetch(`/admin/admin/${adminId}/delete`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('管理员删除成功');
                loadAdminsData(currentAdminPage);
            } else {
                alert('删除失败: ' + (data.error || '未知错误'));
            }
        })
        .catch(error => {
            alert('删除失败: ' + error.message);
        });
    }
}
