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
        this.currentEventSource = null;
        this.currentMessageBubble = null;
        this.streamingEnabled = true; // 流式开关
        
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
        
        if (this.streamingEnabled) {
            await this.sendMessageStream(message);
        } else {
            await this.sendMessageTraditional(message);
        }
    }
    
    addUserMessage(message) {
        const messageElement = this.createMessageElement('user', message);
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }
    
    async sendMessageStream(message) {
        try {
            // 准备SSE请求
            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('message', message);
            formData.append('step', this.currentStep);
            
            // 创建空的AI消息气泡
            this.hideTypingIndicator();
            this.currentMessageBubble = this.createEmptyBotMessage();
            
            // 建立SSE连接
            const response = await fetch('/chat/message/stream', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Stream request failed');
            }
            
            // 处理流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // 处理完整的SSE消息
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // 保留不完整的部分
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        await this.handleStreamChunk(data);
                    }
                }
            }
            
        } catch (error) {
            console.error('Stream failed:', error);
            this.hideTypingIndicator();
            this.addBotMessage('❌ 抱歉，网络连接出现问题，请重试。');
            this.enableInput();
        }
    }
    
    async sendMessageTraditional(message) {
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
            this.enableInput();
        }
    }
    
    async handleStreamChunk(data) {
        if (data.type === 'content') {
            // 追加内容到当前消息
            this.appendToCurrentMessage(data.content);
            
        } else if (data.type === 'progress') {
            // 处理进度更新
            this.updateProgressUI(data);
            
        } else if (data.type === 'complete') {
            // 完成状态处理
            this.currentStep = data.step || 'file_upload';
            this.finalizeCurrentMessage();
            this.hideProgressUI();
            
            if (data.need_files) {
                this.showFileUploadPrompt();
            } else if (data.result) {
                this.showEvaluationResult(data.result);
            } else {
                this.enableInput();
            }
            
        } else if (data.type === 'continue') {
            // 继续对话
            this.currentStep = data.step || 'requirement_confirmation';
            this.finalizeCurrentMessage();
            this.enableInput();
            
        } else if (data.type === 'error') {
            // 错误处理
            this.finalizeCurrentMessage();
            this.hideProgressUI();
            this.addBotMessage('❌ ' + data.message);
            this.enableInput();
            
        } else if (data.type === 'heartbeat') {
            // 心跳消息，保持连接
            // 不需要特别处理，只是保持连接活跃
        }
    }
    
    createEmptyBotMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = '<i class="fas fa-robot"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = '<span class="cursor">▎</span>'; // 光标效果
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        messageContent.appendChild(bubble);
        messageContent.appendChild(time);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        
        return messageDiv;
    }
    
    appendToCurrentMessage(content) {
        if (this.currentMessageBubble) {
            const bubble = this.currentMessageBubble.querySelector('.message-bubble');
            const cursor = bubble.querySelector('.cursor');
            
            if (cursor) {
                // 在光标前插入内容
                cursor.insertAdjacentHTML('beforebegin', content);
            } else {
                // 如果没有光标，直接追加
                bubble.innerHTML += content;
            }
            
            this.scrollToBottom();
        }
    }
    
    finalizeCurrentMessage() {
        if (this.currentMessageBubble) {
            const bubble = this.currentMessageBubble.querySelector('.message-bubble');
            const cursor = bubble.querySelector('.cursor');
            
            if (cursor) {
                cursor.remove(); // 移除光标
            }
            
            // 处理Markdown格式
            bubble.innerHTML = this.convertMarkdownToHtml(bubble.innerHTML);
            
            this.currentMessageBubble = null;
        }
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
            
            this.addBotMessage(`📤 正在上传 ${files.length} 个文件...`);
            this.hideFileUpload();
            
            // 使用流式上传端点
            const response = await fetch('/chat/upload/stream', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Stream request failed');
            }
            
            this.addBotMessage(`✅ 文件上传成功，开始处理...`);
            
            // 处理流式响应
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // 处理完整的SSE消息
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // 保留不完整的部分
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            await this.handleStreamChunk(data);
                        } catch (e) {
                            console.error('Failed to parse stream data:', e);
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error('Upload failed:', error);
            this.hideProgressUI();
            this.addBotMessage('❌ 文件上传失败，请重试。');
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
                    
                    // 显示报告内容
                    this.showReport(data.result);
                    
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
    
    showReport(result) {
        // 显示报告完成消息
        this.addBotMessage('📊 评估报告已生成完成！以下是详细结果：');
        
        // 创建报告显示区域
        const reportMessage = this.createReportMessage(result.report);
        this.chatMessages.appendChild(reportMessage);
        this.scrollToBottom();
        
        // 禁用输入，处理完成
        this.disableInput();
        
        // 添加操作按钮
        this.addActionButtons(result);
    }
    
    createReportMessage(reportContent) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = '<i class="fas fa-chart-bar"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const reportCard = document.createElement('div');
        reportCard.className = 'report-card';
        reportCard.innerHTML = `
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h6 class="mb-0">
                        <i class="fas fa-file-alt"></i> 候选人评估报告
                    </h6>
                </div>
                <div class="card-body">
                    <div class="markdown-content" id="reportContent">
                        ${this.convertMarkdownToHtml(reportContent)}
                    </div>
                </div>
            </div>
        `;
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        messageContent.appendChild(reportCard);
        messageContent.appendChild(time);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        
        return messageDiv;
    }
    
    convertMarkdownToHtml(markdown) {
        if (!markdown) return '<p>报告内容暂不可用</p>';
        
        // 简单的Markdown转HTML
        let html = markdown
            // 标题处理
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // 粗体和斜体
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // 换行处理
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        
        // 处理表格
        html = this.convertMarkdownTable(html);
        
        // 包装段落
        if (!html.includes('<p>') && !html.includes('<h1>') && !html.includes('<h2>') && !html.includes('<h3>')) {
            html = '<p>' + html + '</p>';
        }
        
        return html;
    }
    
    convertMarkdownTable(html) {
        // 查找表格行
        const tableRegex = /(\|[^|\n]*\|[^|\n]*\|[^\n]*\n)+/g;
        
        return html.replace(tableRegex, (match) => {
            const rows = match.trim().split('\n');
            if (rows.length < 2) return match;
            
            let tableHtml = '<table class="table table-striped table-bordered table-sm">';
            
            // 处理表头
            const headerRow = rows[0];
            const headers = headerRow.split('|').map(h => h.trim()).filter(h => h);
            
            tableHtml += '<thead><tr>';
            headers.forEach(header => {
                tableHtml += `<th>${header}</th>`;
            });
            tableHtml += '</tr></thead>';
            
            // 跳过分隔行，处理数据行
            tableHtml += '<tbody>';
            for (let i = 2; i < rows.length; i++) {
                const row = rows[i];
                if (row.trim()) {
                    const cells = row.split('|').map(c => c.trim()).filter(c => c);
                    tableHtml += '<tr>';
                    cells.forEach(cell => {
                        tableHtml += `<td>${cell}</td>`;
                    });
                    tableHtml += '</tr>';
                }
            }
            tableHtml += '</tbody></table>';
            
            return tableHtml;
        });
    }
    
    addActionButtons(result) {
        const actionMessage = document.createElement('div');
        actionMessage.className = 'message bot-message';
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = '<i class="fas fa-tools"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const actionButtons = document.createElement('div');
        actionButtons.className = 'action-buttons';
        actionButtons.innerHTML = `
            <div class="d-flex gap-2 flex-wrap">
                <button class="btn btn-primary btn-sm" onclick="window.print()">
                    <i class="fas fa-print"></i> 打印报告
                </button>
                <button class="btn btn-success btn-sm" onclick="this.downloadReport()">
                    <i class="fas fa-download"></i> 下载报告
                </button>
                <button class="btn btn-info btn-sm" onclick="location.reload()">
                    <i class="fas fa-refresh"></i> 重新开始
                </button>
            </div>
        `;
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        messageContent.appendChild(actionButtons);
        messageContent.appendChild(time);
        actionMessage.appendChild(avatar);
        actionMessage.appendChild(messageContent);
        
        this.chatMessages.appendChild(actionMessage);
        this.scrollToBottom();
    }
    
    updateProgressUI(progressData) {
        const { stage, message, progress, current_item, total_items, completed_items } = progressData;
        
        // 创建或更新进度容器
        let progressContainer = document.getElementById('progress-container');
        if (!progressContainer) {
            progressContainer = this.createProgressContainer();
        }
        
        // 更新进度条
        const progressBar = progressContainer.querySelector('.progress-bar');
        const progressText = progressContainer.querySelector('.progress-text');
        const progressMessage = progressContainer.querySelector('.progress-message');
        const progressDetail = progressContainer.querySelector('.progress-detail');
        
        // 更新进度条
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        
        // 更新文本
        progressText.textContent = `${Math.round(progress)}%`;
        progressMessage.textContent = message;
        
        // 更新详细信息
        if (total_items && completed_items !== undefined) {
            progressDetail.textContent = `${completed_items}/${total_items}`;
            progressDetail.style.display = 'block';
        } else if (current_item) {
            progressDetail.textContent = current_item;
            progressDetail.style.display = 'block';
        } else {
            progressDetail.style.display = 'none';
        }
        
        // 更新阶段样式
        this.updateStageIndicator(stage);
    }

    createProgressContainer() {
        const progressContainer = document.createElement('div');
        progressContainer.id = 'progress-container';
        progressContainer.className = 'progress-container';
        
        progressContainer.innerHTML = `
            <div class="progress-header">
                <span class="progress-title">处理进度</span>
                <span class="progress-text">0%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div class="progress-info">
                <div class="progress-message">正在初始化...</div>
                <div class="progress-detail" style="display: none;"></div>
            </div>
            <div class="progress-stages">
                <div class="stage-indicator" data-stage="initialization">初始化</div>
                <div class="stage-indicator" data-stage="resume_processing">简历处理</div>
                <div class="stage-indicator" data-stage="dimension_generation">维度生成</div>
                <div class="stage-indicator" data-stage="candidate_evaluation">候选人评估</div>
                <div class="stage-indicator" data-stage="report_generation">报告生成</div>
            </div>
        `;
        
        // 插入到聊天消息区域
        this.chatMessages.appendChild(progressContainer);
        this.scrollToBottom();
        
        return progressContainer;
    }

    updateStageIndicator(currentStage) {
        const stageIndicators = document.querySelectorAll('.stage-indicator');
        
        stageIndicators.forEach(indicator => {
            const stage = indicator.getAttribute('data-stage');
            indicator.classList.remove('active', 'completed');
            
            if (stage === currentStage) {
                indicator.classList.add('active');
            } else if (this.isStageCompleted(stage, currentStage)) {
                indicator.classList.add('completed');
            }
        });
    }

    isStageCompleted(stage, currentStage) {
        const stageOrder = [
            'initialization',
            'resume_processing',
            'dimension_generation',
            'candidate_evaluation',
            'report_generation'
        ];
        
        const stageIndex = stageOrder.indexOf(stage);
        const currentIndex = stageOrder.indexOf(currentStage);
        
        return stageIndex < currentIndex;
    }

    hideProgressUI() {
        const progressContainer = document.getElementById('progress-container');
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }
    }

    showEvaluationResult(result) {
        // 隐藏进度UI
        this.hideProgressUI();
        
        // 显示结果摘要
        const resultSummary = `
            ✅ **处理完成**
            
            📊 **评估结果摘要**
            - 候选人数量: ${result.evaluations ? result.evaluations.length : 0}
            - 生成时间: ${new Date().toLocaleString()}
            
            📝 以下是详细的评估报告：
        `;
        
        this.addBotMessage(resultSummary);
        
        // 直接显示报告内容，而不是显示按钮
        if (result.report) {
            this.showReportContent(result.report);
        }
        
        // 添加操作按钮
        this.addDownloadButton(result);
    }

    showReportContent(reportContent) {
        // 直接在聊天窗口中显示报告内容
        const reportMessage = this.createReportMessage(reportContent);
        this.chatMessages.appendChild(reportMessage);
        this.scrollToBottom();
    }

    addDownloadButton(result) {
        const actionMessage = document.createElement('div');
        actionMessage.className = 'message bot-message';
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = '<i class="fas fa-tools"></i>';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        const actionButtons = document.createElement('div');
        actionButtons.className = 'action-buttons';
        
        const buttonContainer = document.createElement('div');
        buttonContainer.className = 'd-flex gap-2 flex-wrap';
        
        // 打印按钮
        const printBtn = document.createElement('button');
        printBtn.className = 'btn btn-primary btn-sm';
        printBtn.innerHTML = '<i class="fas fa-print"></i> 打印报告';
        printBtn.onclick = () => window.print();
        
        // 下载按钮
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'btn btn-success btn-sm';
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> 下载报告';
        downloadBtn.onclick = () => this.downloadReportContent(result.report || '');
        
        // 重新开始按钮
        const restartBtn = document.createElement('button');
        restartBtn.className = 'btn btn-info btn-sm';
        restartBtn.innerHTML = '<i class="fas fa-refresh"></i> 重新开始';
        restartBtn.onclick = () => location.reload();
        
        buttonContainer.appendChild(printBtn);
        buttonContainer.appendChild(downloadBtn);
        buttonContainer.appendChild(restartBtn);
        actionButtons.appendChild(buttonContainer);
        
        const time = document.createElement('div');
        time.className = 'message-time';
        time.textContent = new Date().toLocaleTimeString();
        
        messageContent.appendChild(actionButtons);
        messageContent.appendChild(time);
        actionMessage.appendChild(avatar);
        actionMessage.appendChild(messageContent);
        
        this.chatMessages.appendChild(actionMessage);
        this.scrollToBottom();
    }

    downloadReportContent(reportContent) {
        if (!reportContent) {
            alert('报告内容不可用');
            return;
        }
        
        // 创建下载链接
        const blob = new Blob([reportContent], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `candidate_evaluation_report_${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// 初始化聊天机器人
document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});