// HR智能体聊天界面JavaScript

class ChatBot {
    constructor() {
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.fileBtn = document.getElementById('fileBtn');
        this.fileUploadArea = document.getElementById('fileUploadArea');
        this.resumeFiles = document.getElementById('resumeFiles');
        this.uploadBtn = document.getElementById('uploadBtn');
        this.cancelUploadBtn = document.getElementById('cancelUploadBtn');
        this.statusBadge = document.getElementById('statusBadge');
        
        this.sessionId = null;
        this.currentStep = 'start';
        this.jdText = '';
        this.uploadedFiles = [];
        
        this.init();
    }
    
    init() {
        // 事件监听
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.fileBtn.addEventListener('click', () => this.showFileUpload());
        this.uploadBtn.addEventListener('click', () => this.uploadFiles());
        this.cancelUploadBtn.addEventListener('click', () => this.hideFileUpload());
        
        // 自动调整文本框高度
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // 开始会话
        this.startSession();
    }
    
    async startSession() {
        try {
            const response = await fetch('/chat/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            this.sessionId = data.session_id;
            this.currentStep = data.step;
            
            // 如果有初始消息，显示它
            if (data.message) {
                this.addBotMessage(data.message);
            }
            
        } catch (error) {
            console.error('启动会话失败:', error);
            this.addBotMessage('抱歉，系统启动失败，请刷新页面重试。');
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // 显示用户消息
        this.addUserMessage(message);
        this.messageInput.value = '';
        this.autoResizeTextarea();
        
        // 禁用输入
        this.disableInput();
        
        // 显示输入状态
        this.showTypingIndicator();
        
        try {
            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('message', message);
            formData.append('step', this.currentStep);
            
            const response = await fetch('/chat/message', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            // 隐藏输入状态
            this.hideTypingIndicator();
            
            if (data.status === 'success') {
                // 显示AI回复
                this.addBotMessage(data.message);
                
                // 更新会话状态
                this.currentStep = data.step;
                
                // 检查是否需要上传文件
                if (data.need_files) {
                    this.showFileUploadPrompt();
                }
                
                // 检查是否完成
                if (data.completed) {
                    this.handleCompletion(data);
                }
                
                // 如果是需求确认阶段，继续启用输入
                if (this.currentStep === 'requirement_confirmation') {
                    this.enableInput();
                } else if (this.currentStep === 'file_upload') {
                    // 文件上传阶段禁用文本输入
                    this.disableInput();
                }
                
            } else {
                this.addBotMessage('抱歉，处理您的消息时出现错误，请重试。');
            }
            
        } catch (error) {
            console.error('发送消息失败:', error);
            this.hideTypingIndicator();
            this.addBotMessage('抱歉，网络连接出现问题，请重试。');
            this.enableInput(); // 错误时重新启用输入
        }
    }
    
    addUserMessage(message) {
        const messageElement = this.createMessageElement('user', message);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    addBotMessage(message) {
        const messageElement = this.createMessageElement('bot', message);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    createMessageElement(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = type === 'bot' ? '<i class="fas fa-robot"></i>' : '<i class="fas fa-user"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        // 处理消息内容（支持简单的HTML）
        if (typeof content === 'string') {
            // 简单的Markdown支持
            content = content
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/\n/g, '<br>');
        }
        
        bubble.innerHTML = content;
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        if (type === 'user') {
            messageContent.appendChild(bubble);
            messageContent.appendChild(time);
            messageDiv.appendChild(messageContent);
            messageDiv.appendChild(avatar);
        } else {
            messageContent.appendChild(bubble);
            messageContent.appendChild(time);
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(messageContent);
        }
        
        return messageDiv;
    }
    
    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'message bot-message';
        indicator.id = 'typingIndicator';
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = '<i class="fas fa-robot"></i>';
        
        const content = document.createElement('div');
        content.className = 'message-content';
        
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        
        content.appendChild(typingDiv);
        indicator.appendChild(avatar);
        indicator.appendChild(content);
        
        this.chatMessages.appendChild(indicator);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    showFileUpload() {
        this.fileUploadArea.style.display = 'block';
        this.scrollToBottom();
    }
    
    hideFileUpload() {
        this.fileUploadArea.style.display = 'none';
        this.resumeFiles.value = '';
    }
    
    showFileUploadPrompt() {
        this.addBotMessage('现在请上传候选人的简历文件。您可以点击下方的 📎 按钮或直接拖拽文件到此处。');
        this.showFileUpload();
    }
    
    async uploadFiles() {
        const files = this.resumeFiles.files;
        if (!files || files.length === 0) {
            alert('请先选择要上传的文件');
            return;
        }
        
        const formData = new FormData();
        formData.append('session_id', this.sessionId);
        
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        try {
            this.uploadBtn.disabled = true;
            this.uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 上传中...';
            
            const response = await fetch('/chat/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.addBotMessage(`✅ 成功上传了 ${data.file_count} 个文件。正在开始处理...`);
                this.hideFileUpload();
                
                // 开始处理
                this.startProcessing(data.task_id);
                
            } else {
                this.addBotMessage('❌ 文件上传失败: ' + data.error);
            }
            
        } catch (error) {
            console.error('上传文件失败:', error);
            this.addBotMessage('❌ 文件上传过程中出现错误，请重试。');
        } finally {
            this.uploadBtn.disabled = false;
            this.uploadBtn.innerHTML = '<i class="fas fa-upload"></i> 上传文件';
        }
    }
    
    async startProcessing(taskId) {
        this.addBotMessage('🔄 正在处理您的简历，请稍等...');
        this.statusBadge.textContent = '处理中';
        this.statusBadge.className = 'badge bg-warning ms-2';
        
        // 轮询处理状态
        const pollStatus = async () => {
            try {
                const response = await fetch(`/chat/status/${taskId}`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    this.addBotMessage('✅ 处理完成！正在生成评估报告...');
                    this.statusBadge.textContent = '完成';
                    this.statusBadge.className = 'badge bg-success ms-2';
                    
                    // 跳转到结果页面
                    setTimeout(() => {
                        window.location.href = `/result/${taskId}`;
                    }, 2000);
                    
                } else if (data.status === 'failed') {
                    this.addBotMessage('❌ 处理失败: ' + data.error);
                    this.statusBadge.textContent = '失败';
                    this.statusBadge.className = 'badge bg-danger ms-2';
                    
                } else {
                    // 继续轮询
                    setTimeout(pollStatus, 2000);
                }
                
            } catch (error) {
                console.error('检查状态失败:', error);
                this.addBotMessage('❌ 状态检查失败，请刷新页面重试。');
                this.statusBadge.textContent = '错误';
                this.statusBadge.className = 'badge bg-danger ms-2';
            }
        };
        
        pollStatus();
    }
    
    handleCompletion(data) {
        if (data.result_url) {
            this.addBotMessage('🎉 简历筛选完成！正在跳转到结果页面...');
            setTimeout(() => {
                window.location.href = data.result_url;
            }, 2000);
        }
    }
    
    autoResizeTextarea() {
        const textarea = this.messageInput;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }
    
    enableInput() {
        this.messageInput.disabled = false;
        this.sendBtn.disabled = false;
        this.messageInput.focus();
    }
    
    disableInput() {
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
    }
}

// 初始化聊天机器人
document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});