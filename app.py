# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from agent.ai_agent import get_agent_service, clear_user_agent_sessions, get_agent_memory_stats
from agent.attraction_guide import get_attraction_guide_response_stream, clear_tour_guide_agents
from database_self import db
import os
import json
from dotenv import load_dotenv
import uuid
import random
import smtplib
from email.mime.text import MIMEText
#from datetime import datetime, timedelta
from werkzeug.security import check_password_hash

# 加载环境变量
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')


# 邮件配置
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SENDER_EMAIL = os.getenv('SENDER_EMAIL')


# ------------------------ 邮箱验证函数 ------------------------
def send_verification_email(email, code):
    """发送验证码到指定邮箱"""
    try:
        if not SMTP_SERVER or not SMTP_PORT or not SMTP_USERNAME or not SMTP_PASSWORD or not SENDER_EMAIL:
            print("SMTP配置不完整，请检查环境变量")
            raise ValueError("SMTP配置不完整，请检查环境变量")
        
        subject = "青鸾向导 - 注册验证码"
        body = f"您的注册验证码是: {code}\n验证码在5分钟内有效，请尽快完成注册。"
        
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = email
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [email], msg.as_string())
        
        return True
        
    except Exception as e:
        print(f"发送邮件失败: {str(e)}")
        return False



# ------------------------ 用户功能函数 ------------------------
def clear_user_agents(email):
    """清除用户的智能体会话和Redis记忆"""
    return clear_user_agent_sessions(email)

def add_user(email, password):
    return db.add_user(email, password)

def verify_user(email, password):
    return db.verify_user(email, password)

def save_conversation(email, messages, conv_id):
    db.save_conversation(email, messages, conv_id)

def get_history(email):
    return db.get_history(email)

def clear_user_history(email):
    """清理用户的所有数据：SQLite历史记录 + Redis智能体记忆"""
    # 1. 清理SQLite数据库中的历史记录
    success = db.clear_user_history(email)
    
    # 2. 清理Redis中的智能体记忆
    if success:
        clear_user_agents(email)
    
    return success

def new_conversation(email):
    session['current_conv_id'] = str(uuid.uuid4())
    return True

# ------------------------ 工具函数 ------------------------
def stream_response(generator, user_message, email, conv_id, agent_type):
    def generate():
        try:
            full_response = ""
            for chunk in generator:
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            save_conversation(email, [
                {"text": user_message, "is_user": True, "agent_type": agent_type},
                {"text": full_response, "is_user": False, "agent_type": agent_type},
            ], conv_id)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

# ------------------------ 路由 ------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if verify_user(email, password):
            session['email'] = email
            # 更新最后登录时间
            db.update_user_last_login(email)
            return redirect(url_for('chat'))
        return render_template('login.html', error="未注册或账号、密码错误")
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('password2', '').strip()
    verification_code = request.form.get('verification_code', '').strip()

    allowed_domains = ['@qq.com', '@gmail.com', '@outlook.com', '@163.com', '@foxmail.com']

    if not email or not password or not confirm_password:
        return render_template('login.html', error="所有字段都必须填写")
    if password != confirm_password:
        return render_template('login.html', error="两次输入的密码不一致")
    if '@' not in email or not any(email.endswith(domain) for domain in allowed_domains):
        return render_template('login.html', error="仅支持指定邮箱后缀注册")
    # 验证验证码
    if not db.verify_code(email, verification_code):
        return render_template('login.html', error="验证码错误或已过期")
    if add_user(email, password):
        session['email'] = email
        db.update_user_last_login(email)
        return redirect(url_for('chat'))
    return render_template('login.html', error="账号已存在")

@app.route('/chat')
def chat():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html', email=session['email'])

@app.route('/travel')
def travel():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('travel.html', email=session['email'])

@app.route('/send_message', methods=['POST'])
def send_message():
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_message = data.get("message", "").strip()
    agent_type = data.get("agent_type", "general")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    email = session["email"]
    conv_id = session.get("current_conv_id") or str(uuid.uuid4())
    session["current_conv_id"] = conv_id

    try:
        agent_service = get_agent_service()
        generator = agent_service.get_response_stream(user_message, email, agent_type, conv_id)
        return stream_response(generator, user_message, email, conv_id, agent_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/attraction_guide', methods=['POST'])
def attraction_guide():
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    email = session["email"]
    conv_id = session.get("current_conv_id") or str(uuid.uuid4())
    session["current_conv_id"] = conv_id

    try:
        generator = get_attraction_guide_response_stream(user_message, email)
        return stream_response(generator, user_message, email, conv_id, "attraction_guide")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/plan_travel', methods=['POST'])
def plan_travel():
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    from agent.prompts import format_travel_request_prompt

    data = request.get_json()
    travel_message = format_travel_request_prompt(data)

    email = session["email"]
    conv_id = session.get("current_conv_id") or str(uuid.uuid4())
    session["current_conv_id"] = conv_id

    try:
        agent_service = get_agent_service()
        generator = agent_service.get_response_stream(travel_message, email, "travel", conv_id)
        return stream_response(generator, travel_message, email, conv_id, "travel")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/load_history', methods=['POST'])
def load_history():
    if 'email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        return jsonify({'history': get_history(session['email'])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_conversation', methods=['POST'])
def delete_conversation():
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return jsonify({"error": "Missing conversation_id"}), 400

    try:
        success = db.delete_conversation_for_user(session["email"], conversation_id)
        if success:
            return jsonify({"success": True})
        return jsonify({"error": "Conversation not found or access denied"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/clear_history', methods=['POST'])
def clear_history():
    if "email" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    clear_user_history(session["email"])
    session.pop("current_conv_id", None)
    return jsonify({"success": True})

@app.route('/new_conversation', methods=['POST'])
def start_new_conversation():
    if 'email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        new_conversation(session['email'])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    email = session.get('email')
    if email:
        clear_user_agents(email)
        clear_tour_guide_agents(email)
    session.clear()
    return redirect(url_for('login'))

@app.route('/memory_stats', methods=['GET'])
def memory_stats():
    """获取记忆系统统计信息（管理员接口）"""
    if 'email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        stats = get_agent_memory_stats()
        return jsonify({
            'status': 'success',
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
        
        
# 新路由：发送验证码
@app.route('/send_verification_code', methods=['POST'])
def send_verification_code():
    data = request.get_json()
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'status': 'error', 'message': '邮箱不能为空'}), 400
    
    # 生成验证码
    code = str(random.randint(100000, 999999))
    
    # 发送邮件
    if send_verification_email(email, code):
        db.save_verification_code(email, code, expiry_seconds=300)
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': '发送验证码失败，请检查邮箱是否正确'}), 500
    
    
# ------------------------ 后台管理接口 ------------------------
# 后台管理路由,如果是从index.html跳转过来，直接渲染登录页面
@app.route('/admin_login', methods=['POST', 'GET'])
def admin_login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        username = data.get('email')
        # # 这里用了哈希验证来检查密码
        # if check_password_hash(ADMIN_EMAIL_HASH, email) and check_password_hash(ADMIN_PASSWORD_HASH, password):
        #     session['is_admin'] = True
        #     return jsonify({'success': True})
        # else:
        #     return jsonify({'success': False, 'message': '邮箱或密码错误'})
        # 这里用了哈希验证来检查密码
        if db.verify_admin(username, password):
            session['is_admin'] = True
            session['admin_username'] = username
            
            # 更新最后登录时间
            admin_info = db.get_admin_by_username(username)
            db.update_admin_last_login(email)
            if admin_info:
                db.log_admin_action(
                    admin_info['id'], 
                    'LOGIN', 
                    details="管理员登录系统"
                )
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': '用户名或密码错误'})
    return render_template('admin_login.html')

@app.route('/admin')
def admin():
    # 权限检查
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    # 后台仪表盘页面渲染
    return render_template('admin.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin/users')
def admin_users():
    """获取用户列表（分页）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    users_data = db.get_users(page, per_page)
    return jsonify(users_data)

@app.route('/admin/user/<email>')
def admin_user_detail(email):
    """获取用户详情"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_details = db.get_user_details(email)
    if user_details:
        return jsonify(user_details)
    return jsonify({'error': 'User not found'}), 404

@app.route('/admin/conversations')
def admin_conversations():
    """获取会话列表（分页）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    conversations_data = db.get_conversations(page, per_page)
    return jsonify(conversations_data)

@app.route('/admin/messages')
def admin_messages():
    """获取消息列表（分页）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    messages_data = db.get_messages(page, per_page)
    return jsonify(messages_data)

@app.route('/admin/stats')
def admin_stats():
    """获取系统统计数据"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    stats = db.get_system_stats()
    return jsonify(stats)


# 新增路由：获取会话详情
@app.route('/admin/conversation/<conv_id>')
def admin_conversation_detail(conv_id):
    """获取会话详情"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # 获取会话基本信息
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.user_email, c.date, c.created_at, 
                   COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.id = ?
            GROUP BY c.id
        ''', (conv_id,))
        conversation = cursor.fetchone()
        
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        
        # 获取会话的所有消息
        cursor.execute('''
            SELECT m.id, m.text, m.is_user, m.agent_type, m.created_at
            FROM messages m
            WHERE m.conversation_id = ?
            ORDER BY m.created_at ASC
        ''', (conv_id,))
        messages = [dict(row) for row in cursor.fetchall()]
        
        return jsonify({
            'conversation': dict(conversation),
            'messages': messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增路由：删除用户
@app.route('/admin/user/<email>/delete', methods=['DELETE'])
def admin_delete_user(email):
    """删除用户及其所有数据"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # 1. 清除用户的所有会话和消息
        success = db.clear_user_history(email)
        
        # 2. 删除用户
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE email = ?', (email,))
        conn.commit()
        
        if cursor.rowcount > 0:
            # 3. 清除Redis中的智能体记忆
            clear_user_agents(email)
            clear_tour_guide_agents(email)
            return jsonify({'success': True})
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增路由：删除会话
@app.route('/admin/conversation/<conv_id>/delete', methods=['DELETE'])
def admin_delete_conversation(conv_id):
    """删除会话及其所有消息"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # 获取会话所属用户邮箱
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_email FROM conversations WHERE id = ?', (conv_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Conversation not found'}), 404
        
        email = result['user_email']
        
        # 删除会话
        if db.delete_conversation(conv_id):
            # 清除Redis中的相关记忆
            clear_user_agents(email)
            clear_tour_guide_agents(email)
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to delete conversation'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增路由：删除消息
@app.route('/admin/message/<int:message_id>/delete', methods=['DELETE'])
def admin_delete_message(message_id):
    """删除单条消息"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 获取消息所属会话ID
        cursor.execute('SELECT conversation_id FROM messages WHERE id = ?', (message_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'Message not found'}), 404
        
        conv_id = result['conversation_id']
        
        # 删除消息
        cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            # 获取会话所属用户邮箱
            cursor.execute('SELECT user_email FROM conversations WHERE id = ?', (conv_id,))
            conv_result = cursor.fetchone()
            
            if conv_result:
                email = conv_result['user_email']
                # 清除Redis中的相关记忆
                clear_user_agents(email)
                clear_tour_guide_agents(email)
            
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to delete message'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增搜索路由
@app.route('/admin/search', methods=['GET'])
def admin_search():
    """统一搜索接口"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        search_type = request.args.get('type', 'users')  # users, conversations, messages
        query = request.args.get('query', '')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        if not query:
            return jsonify({'error': 'Empty query'}), 400
        
        # 用户搜索
        if search_type == 'users':
            users = db.search_users(query, page, per_page)
            return jsonify(users)
        
        # 会话搜索
        elif search_type == 'conversations':
            conversations = db.search_conversations(query, page, per_page)
            return jsonify(conversations)
        
        # 消息搜索
        elif search_type == 'messages':
            messages = db.search_messages(query, page, per_page)
            return jsonify(messages)
        
        return jsonify({'error': 'Invalid search type'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 新增管理员管理路由
@app.route('/admin/admins')
def admin_admins():
    """获取管理员列表（分页）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    admins_data = db.get_admins(page, per_page)
    return jsonify(admins_data)

@app.route('/admin/admin/add', methods=['POST'])
def admin_add_admin():
    """添加新管理员"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    role = data.get('role', 'admin')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码是必填项'}), 400
    
    # 记录操作日志
    current_admin = session.get('admin_username')
    admin_info = db.get_admin_by_username(current_admin)
    
    if admin_info:
        db.log_admin_action(
            admin_info['id'], 
            'ADD_ADMIN', 
            target_id=f'{username}',
            details=f"添加管理员: {username} ({role})"
        )
    
    if db.add_admin(username, password, email, role):
        return jsonify({'success': True})
    return jsonify({'error': '添加管理员失败，用户名可能已存在'}), 400

@app.route('/admin/admin/<int:admin_id>/update', methods=['POST'])
def admin_update_admin(admin_id):
    """更新管理员信息"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    email = data.get('email')
    role = data.get('role')
    password = data.get('password')
    
    # 记录操作日志
    current_admin = session.get('admin_username')
    admin_info = db.get_admin_by_username(current_admin)
    
    if admin_info:
        target_admin = db.get_admin_by_id(admin_id)
        log_details = f"更新管理员: {target_admin['username'] if target_admin else admin_id}"
        
        if email:
            log_details += f", 邮箱: {email}"
        if role:
            log_details += f", 角色: {role}"
        if password:
            log_details += ", 重置了密码"
        
        db.log_admin_action(
            admin_info['id'], 
            'UPDATE_ADMIN', 
            target_id=admin_id,
            details=log_details
        )
    
    if db.update_admin(admin_id, email, role, password):
        return jsonify({'success': True})
    return jsonify({'error': '更新管理员失败'}), 400

@app.route('/admin/admin/<int:admin_id>/delete', methods=['DELETE'])
def admin_delete_admin(admin_id):
    """删除管理员，若角色为 superadmin 则不允许删除"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # 记录操作日志
    current_admin = session.get('admin_username')
    admin_info = db.get_admin_by_username(current_admin)
    target_admin = db.get_admin_by_id(admin_id)
    
    if admin_info and target_admin:
        db.log_admin_action(
            admin_info['id'], 
            'DELETE_ADMIN', 
            target_id=admin_id,
            details=f"删除管理员: {target_admin['username']}"
        )
    
    if db.delete_admin(admin_id):
        return jsonify({'success': True})
    return jsonify({'error': '删除管理员失败'}), 400

@app.route('/admin/logs')
def admin_logs():
    """获取管理员操作日志（分页）"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    logs_data = db.get_admin_logs(page, per_page)
    return jsonify(logs_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
