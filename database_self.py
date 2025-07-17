import os
import sqlite3
#import json
from datetime import datetime, timedelta
#import os
from typing import List, Dict, Any#, Optional
#import time

class Database:
    def __init__(self, db_path: str = 'app.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    
    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 启用外键约束
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # 创建对话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users (email) ON DELETE CASCADE
            )
        ''')
        
        # 创建消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                text TEXT NOT NULL,
                is_user BOOLEAN NOT NULL,
                agent_type TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        ''')
        
        # 创建验证码表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_verifications (
                email TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        
        # 创建管理员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # 创建管理员操作日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES admins (id)
            )
        ''')
        
        # 检查初始管理员是否存在
        self.create_initial_admin()
        
        # # 创建索引以提高查询性能
        # cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversations_user_email ON conversations (user_email)')
        # cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id)')
        # cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)')
        
        conn.commit()
        conn.close()
    
    def add_user(self, email: str, password: str) -> bool:
        """添加新用户"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'INSERT INTO users (email, password, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (email, password, now_str, now_str)
            )
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 用户已存在
            conn.close()
            return False
        except Exception as e:
            print(f"Error adding user: {e}")
            conn.close()
            return False
    
    def verify_user(self, email: str, password: str) -> bool:
        """验证用户登录"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT password FROM users WHERE email = ?',
                (email,)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result['password'] == password:
                return True
            return False
        except Exception as e:
            print(f"Error verifying user: {e}")
            conn.close()
            return False
    
    def save_conversation(self, email: str, messages: List[Dict[str, Any]], conv_id: str):
        """保存对话和消息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 检查对话是否已存在
            cursor.execute(
                'SELECT id FROM conversations WHERE id = ?',
                (conv_id,)
            )
            
            if not cursor.fetchone():
                # 创建新对话
                cursor.execute(
                    'INSERT INTO conversations (id, user_email, date, created_at) VALUES (?, ?, ?, ?)',
                    (conv_id, email, today, now_str)
                )
            
            # 保存消息
            for message in messages:
                cursor.execute(
                    'INSERT INTO messages (conversation_id, text, is_user, agent_type, created_at) VALUES (?, ?, ?, ?, ?)',
                    (
                        conv_id,
                        message.get('text', ''),
                        message.get('is_user', False),
                        message.get('agent_type', 'general'),
                        now_str
                    )
                )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error saving conversation: {e}")
            conn.close()
            raise
    
    def get_history(self, email: str) -> List[Dict[str, Any]]:
        """获取用户的历史对话"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取所有对话及其消息
            cursor.execute('''
                SELECT 
                    c.id,
                    c.date,
                    c.created_at,
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_email = ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
            ''', (email,))
            
            conversations = []
            for row in cursor.fetchall():
                # 获取对话的消息
                cursor.execute('''
                    SELECT text, is_user, agent_type, created_at
                    FROM messages 
                    WHERE conversation_id = ?
                    ORDER BY created_at ASC
                ''', (row['id'],))
                
                messages = []
                for msg_row in cursor.fetchall():
                    messages.append({
                        'text': msg_row['text'],
                        'is_user': bool(msg_row['is_user']),
                        'agent_type': msg_row['agent_type'],
                        'created_at': msg_row['created_at']
                    })
                
                conversations.append({
                    'id': row['id'],
                    'date': row['date'],
                    'created_at': row['created_at'],
                    'message_count': row['message_count'],
                    'messages': messages
                })
            
            conn.close()
            return conversations
        except Exception as e:
            print(f"Error getting history: {e}")
            conn.close()
            return []
    
    def clear_user_history(self, email: str) -> bool:
        """清除用户的所有历史记录"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            #首先删除所有与会话相关的消息
            cursor.execute(
                'DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_email = ?)',
                (email,)
            )
            
            # 删除用户的所有对话（消息会通过外键约束自动删除）
            cursor.execute(
                'DELETE FROM conversations WHERE user_email = ?',
                (email,)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error clearing user history: {e}")
            conn.close()
            return False
    
    def get_conversation_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """获取特定对话的所有消息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT text, is_user, agent_type, created_at
                FROM messages 
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            ''', (conv_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'text': row['text'],
                    'is_user': bool(row['is_user']),
                    'agent_type': row['agent_type'],
                    'created_at': row['created_at']
                })
            
            conn.close()
            return messages
        except Exception as e:
            print(f"Error getting conversation messages: {e}")
            conn.close()
            return []
    
    def delete_conversation(self, conv_id: str) -> bool:
        """删除特定对话"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 首先删除该对话的所有消息
            cursor.execute(
                'DELETE FROM messages WHERE conversation_id = ?',
                (conv_id,)
            )
            
            # 然后删除对话本身
            cursor.execute(
                'DELETE FROM conversations WHERE id = ?',
                (conv_id,)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting conversation: {e}")
            conn.close()
            return False
    
    def delete_conversation_for_user(self, email: str, conv_id: str) -> bool:
        """删除特定用户的特定对话（验证权限）"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 首先验证对话是否属于该用户
            cursor.execute(
                'SELECT id FROM conversations WHERE id = ? AND user_email = ?',
                (conv_id, email)
            )
            
            if not cursor.fetchone():
                conn.close()
                return False  # 对话不存在或不属于该用户
            
            # 删除该对话的所有消息
            cursor.execute(
                'DELETE FROM messages WHERE conversation_id = ?',
                (conv_id,)
            )
            
            # 删除对话本身
            cursor.execute(
                'DELETE FROM conversations WHERE id = ? AND user_email = ?',
                (conv_id, email)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error deleting conversation for user: {e}")
            conn.close()
            return False
    
    def get_user_stats(self, email: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 总对话数
            cursor.execute(
                'SELECT COUNT(*) as conv_count FROM conversations WHERE user_email = ?',
                (email,)
            )
            conv_count = cursor.fetchone()['conv_count']
            
            # 总消息数
            cursor.execute('''
                SELECT COUNT(*) as msg_count 
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.user_email = ?
            ''', (email,))
            msg_count = cursor.fetchone()['msg_count']
            
            # 最近活跃时间
            cursor.execute('''
                SELECT MAX(created_at) as last_active
                FROM conversations 
                WHERE user_email = ?
            ''', (email,))
            last_active = cursor.fetchone()['last_active']
            
            conn.close()
            
            return {
                'conversation_count': conv_count,
                'message_count': msg_count,
                'last_active': last_active
            }
        except Exception as e:
            print(f"Error getting user stats: {e}")
            conn.close()
            return {
                'conversation_count': 0,
                'message_count': 0,
                'last_active': None
            }
            
    def save_verification_code(self, email: str, code: str, expiry_seconds: int = 300) -> bool:
        """保存验证码到数据库，默认有效期5分钟"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            expires_at = datetime.now() + timedelta(seconds=expiry_seconds)

            cursor.execute('''
                INSERT OR REPLACE INTO email_verifications (email, code, expires_at)
                VALUES (?, ?, ?)
            ''', (email, code, expires_at))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving verification code: {e}")
            conn.close()
            return False
    
    def verify_code(self, email: str, code: str) -> bool:
        """验证验证码是否正确且未过期"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT code, expires_at FROM email_verifications 
                WHERE email = ?
            ''', (email,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result['code'] == code:
                # 检查是否过期
                if datetime.now() < datetime.fromisoformat(result['expires_at']):
                    return True
            
            return False
        except Exception as e:
            print(f"Error verifying code: {e}")
            conn.close()
            return False
        
    def cleanup_expired_codes(self):
        """清理过期的验证码"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM email_verifications 
                WHERE expires_at < ?
            ''', (datetime.now(),))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error cleaning up expired codes: {e}")
            conn.close()
            
    # 更新用户最后登录时间
    def update_user_last_login(self, email: str):
        """更新用户最后登录时间"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE users SET last_login = ? WHERE email = ?',
                (now_str, email)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating last login: {e}")
            return False
        
    # 获取用户列表（分页）
    def get_users(self, page=1, per_page=10):
        """获取用户列表（分页）"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取用户数据
            cursor.execute('''
                SELECT id, email, created_at, last_login
                FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            users = [dict(row) for row in cursor.fetchall()]
            
            # 获取总用户数
            cursor.execute('SELECT COUNT(*) as total FROM users')
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        except Exception as e:
            print(f"Error getting users: {e}")
            return {'users': [], 'total': 0}
        
    # 获取用户详情
    def get_user_details(self, email: str):
        """获取用户详情及统计数据"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取用户基本信息
            cursor.execute(
                'SELECT id, email, created_at, last_login FROM users WHERE email = ?',
                (email,)
            )
            user = dict(cursor.fetchone())
            
            # 获取用户统计信息
            cursor.execute(
                'SELECT COUNT(*) as conv_count FROM conversations WHERE user_email = ?',
                (email,)
            )
            conv_count = cursor.fetchone()['conv_count']
            
            cursor.execute('''
                SELECT COUNT(*) as msg_count 
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.user_email = ?
            ''', (email,))
            msg_count = cursor.fetchone()['msg_count']
            
            # 获取用户会话记录
            cursor.execute('''
                SELECT id, date, created_at
                FROM conversations
                WHERE user_email = ?
                ORDER BY created_at DESC
                LIMIT 10
            ''', (email,))
            conversations = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'user': user,
                'stats': {
                    'conv_count': conv_count,
                    'msg_count': msg_count,
                    'avg_msg_per_conv': msg_count / conv_count if conv_count > 0 else 0
                },
                'conversations': conversations
            }
        except Exception as e:
            print(f"Error getting user details: {e}")
            return None
        
    # 获取会话列表（分页）
    def get_conversations(self, page=1, per_page=10):
        """获取会话列表（分页）"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取会话数据
            cursor.execute('''
                SELECT c.id, c.user_email, c.date, c.created_at, 
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            conversations = [dict(row) for row in cursor.fetchall()]
            
            # 获取总会话数
            cursor.execute('SELECT COUNT(*) as total FROM conversations')
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'conversations': conversations,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        except Exception as e:
            print(f"Error getting conversations: {e}")
            return {'conversations': [], 'total': 0}
    
    # 获取消息列表（分页）
    def get_messages(self, page=1, per_page=10):
        """获取消息列表（分页）"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 获取消息数据
            cursor.execute('''
                SELECT m.id, m.conversation_id, m.text, m.is_user, 
                       m.agent_type, m.created_at, c.user_email
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                ORDER BY m.created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            messages = [dict(row) for row in cursor.fetchall()]
            
            # 获取总消息数
            cursor.execute('SELECT COUNT(*) as total FROM messages')
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'messages': messages,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        except Exception as e:
            print(f"Error getting messages: {e}")
            return {'messages': [], 'total': 0}
    
    # 获取系统统计数据
    def get_system_stats(self):
        """获取系统统计数据"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 总用户数
            cursor.execute('SELECT COUNT(*) as total_users FROM users')
            total_users = cursor.fetchone()['total_users']
            
            # 活跃用户数（最近7天登录过）
            seven_days_ago = datetime.now() - timedelta(days=7)
            cursor.execute(
                'SELECT COUNT(*) as active_users FROM users WHERE last_login > ?',
                (seven_days_ago,)
            )
            active_users = cursor.fetchone()['active_users']
            
            # 总会话数
            cursor.execute('SELECT COUNT(*) as total_conversations FROM conversations')
            total_conversations = cursor.fetchone()['total_conversations']
            
            # 总消息数
            cursor.execute('SELECT COUNT(*) as total_messages FROM messages')
            total_messages = cursor.fetchone()['total_messages']
            
            # 最近活跃用户（最近登录的5个用户）
            cursor.execute('''
                SELECT email, last_login 
                FROM users 
                ORDER BY last_login DESC 
                LIMIT 5
            ''')
            recent_users = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_conversations': total_conversations,
                'total_messages': total_messages,
                'recent_users': recent_users
            }
        except Exception as e:
            print(f"Error getting system stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'total_conversations': 0,
                'total_messages': 0,
                'recent_users': []
            }
    
    #后台管理系统的搜索功能        
    def search_users(self, query: str, page=1, per_page=10):
        """搜索用户"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 搜索条件：邮箱
            cursor.execute('''
                SELECT id, email, created_at, last_login
                FROM users
                WHERE email LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (f'%{query}%', per_page, offset))
            
            users = [dict(row) for row in cursor.fetchall()]
            
            # 获取总数
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM users 
                WHERE email LIKE ?
            ''', (f'%{query}%',))
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'users': users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'query': query
            }
        except Exception as e:
            print(f"Error searching users: {e}")
            return {'users': [], 'total': 0}

    def search_conversations(self, query: str, page=1, per_page=10):
        """搜索会话"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 搜索条件：会话ID、用户邮箱
            cursor.execute('''
                SELECT c.id, c.user_email, c.date, c.created_at, 
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.id LIKE ? OR c.user_email LIKE ?
                GROUP BY c.id
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
            ''', (f'%{query}%', f'%{query}%', per_page, offset))
            
            conversations = [dict(row) for row in cursor.fetchall()]
            
            # 获取总数
            cursor.execute('''
                SELECT COUNT(DISTINCT c.id) as total
                FROM conversations c
                WHERE c.id LIKE ? OR c.user_email LIKE ?
            ''', (f'%{query}%', f'%{query}%'))
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'conversations': conversations,
                'total': total,
                'page': page,
                'per_page': per_page,
                'query': query
            }
        except Exception as e:
            print(f"Error searching conversations: {e}")
            return {'conversations': [], 'total': 0}

    def search_messages(self, query: str, page=1, per_page=10):
        """搜索消息"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 搜索条件：消息内容、用户邮箱、会话ID
            cursor.execute('''
                SELECT m.id, m.conversation_id, m.text, m.is_user, 
                    m.agent_type, m.created_at, c.user_email
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.text LIKE ? OR c.user_email LIKE ? OR m.conversation_id LIKE ?
                ORDER BY m.created_at DESC
                LIMIT ? OFFSET ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%', per_page, offset))
            
            messages = [dict(row) for row in cursor.fetchall()]
            
            # 获取总数
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE m.text LIKE ? OR c.user_email LIKE ? OR m.conversation_id LIKE ?
            ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'messages': messages,
                'total': total,
                'page': page,
                'per_page': per_page,
                'query': query
            }
        except Exception as e:
            print(f"Error searching messages: {e}")
            return {'messages': [], 'total': 0}

    def create_initial_admin(self):
            """创建初始管理员账号"""
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                
                # 检查是否已有管理员
                cursor.execute('SELECT COUNT(*) as count FROM admins')
                count = cursor.fetchone()['count']
                now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if count == 0:
                    # 从环境变量获取初始管理员信息
                    initial_username = os.getenv('INITIAL_ADMIN_USERNAME', 'admin')
                    initial_password = os.getenv('INITIAL_ADMIN_PASSWORD', 'admin123')
                    initial_email = os.getenv('INITIAL_ADMIN_EMAIL', 'admin@qq.com')
                    
                    print(f"创建初始管理员: {initial_username}, {initial_email}")
                    # 添加初始管理员
                    from werkzeug.security import generate_password_hash
                    hashed_password = generate_password_hash(initial_password)
                    
                    cursor.execute(
                        'INSERT INTO admins (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)',
                        (initial_username, hashed_password, initial_email, 'superadmin', now_str)
                    )
                    conn.commit()
                
                conn.close()
            except Exception as e:
                print(f"创建初始管理员失败: {e}")
    
    # 管理员管理方法
    def add_admin(self, username: str, password: str, email: str, role: str = 'admin') -> bool:
        """添加新管理员"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            from werkzeug.security import generate_password_hash
            hashed_password = generate_password_hash(password)
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'INSERT INTO admins (username, password, email, role, created_at) VALUES (?, ?, ?, ?, ?)',
                (username, hashed_password, email, role, now_str)
            )
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # 管理员已存在
            conn.close()
            return False
        except Exception as e:
            print(f"添加管理员失败: {e}")
            return False
    
    def verify_admin(self, username_or_email: str, password: str) -> bool:
        """验证管理员登录"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # cursor.execute(
            #     'SELECT password FROM admins WHERE username = ?',
            #     (username,)
            # )
            cursor.execute(
                '''
                SELECT password FROM admins 
                WHERE username = ? OR email = ?
                ''',
                (username_or_email, username_or_email)
            )
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                from werkzeug.security import check_password_hash
                return check_password_hash(result['password'], password)
            return False
        except Exception as e:
            print(f"验证管理员失败: {e}")
            return False
    
    def get_admin_by_username(self, username: str) -> dict:
        """获取管理员信息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT id, username, email, role, created_at, last_login FROM admins WHERE username = ?',
                (username,)
            )
            
            admin = cursor.fetchone()
            conn.close()
            
            if admin:
                return dict(admin)
            return None
        except Exception as e:
            print(f"获取管理员信息失败: {e}")
            return None
    
    def get_admin_by_id(self, admin_id):
        """根据ID获取管理员信息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT id, username, email, role, created_at, last_login FROM admins WHERE id = ?',
                (admin_id,)
            )
            
            admin = cursor.fetchone()
            conn.close()
            
            if admin:
                return dict(admin)
            return None
        except Exception as e:
            print(f"获取管理员信息失败: {e}")
            return None
    
    def get_admins(self, page=1, per_page=10):
        """获取管理员列表（分页）"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, username, email, role, created_at, last_login
                FROM admins
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            admins = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute('SELECT COUNT(*) as total FROM admins')
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'admins': admins,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        except Exception as e:
            print(f"获取管理员列表失败: {e}")
            return {'admins': [], 'total': 0}
    
    def update_admin(self, admin_id: int, email: str = None, role: str = None, password: str = None) -> bool:
        """更新管理员信息"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            updates = []
            params = []
            
            if email:
                updates.append("email = ?")
                params.append(email)
            
            if role:
                updates.append("role = ?")
                params.append(role)
            
            if password:
                from werkzeug.security import generate_password_hash
                hashed_password = generate_password_hash(password)
                updates.append("password = ?")
                params.append(hashed_password)
            
            if not updates:
                return False
                
            params.append(admin_id)
            
            query = f"UPDATE admins SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新管理员失败: {e}")
            return False
    
    def delete_admin(self, admin_id: int) -> bool:
        """删除管理员"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 查询管理员角色
            cursor.execute('SELECT role FROM admins WHERE id = ?', (admin_id,))
            result = cursor.fetchone()

            if result is None:
                # 管理员不存在
                conn.close()
                return False

            role = result[0]
            if role == 'superadmin':
                # 不能删除超级管理员
                conn.close()
                return False
            cursor.execute('DELETE FROM admins WHERE id = ?', (admin_id,))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除管理员失败: {e}")
            return False
    
    def log_admin_action(self, admin_id: int, action: str, target_type: str = None, target_id: str = None, details: str = None):
        """记录管理员操作日志"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO admin_logs (admin_id, action, target_type, target_id, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_id, action, target_type, target_id, details, now_str))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"记录管理员操作日志失败: {e}")
            return False
    
    def get_admin_logs(self, page=1, per_page=10):
        """获取管理员操作日志（分页）"""
        offset = (page - 1) * per_page
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT l.id, l.action, l.target_type, l.target_id, l.details, l.created_at,
                       a.username as admin_username
                FROM admin_logs l
                JOIN admins a ON l.admin_id = a.id
                ORDER BY l.created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
            
            logs = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute('SELECT COUNT(*) as total FROM admin_logs')
            total = cursor.fetchone()['total']
            
            conn.close()
            
            return {
                'logs': logs,
                'total': total,
                'page': page,
                'per_page': per_page
            }
        except Exception as e:
            print(f"获取管理员日志失败: {e}")
            return {'logs': [], 'total': 0}
    
    def update_admin_last_login(self, email: str):
        """更新管理员最后登录时间"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                'UPDATE admins SET last_login = ? WHERE email = ?',
                (now_str, email)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"更新管理员最后登录时间失败: {e}")
            return False

            
# 创建全局数据库实例
db = Database() 
