// HR AI Chat Interface JavaScript

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
        this.streamingEnabled = true; // Streaming switch
        
        this.init();
    }
    
    init() {
        // Event listeners
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
        
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.autoResizeTextarea());
        
        // Start session
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
            
            // If there's an initial message, display it
            if (data.message) {
                this.addBotMessage(data.message);
            }
            
        } catch (error) {
            console.error('Failed to start session:', error);
            this.addBotMessage('Sorry, system startup failed. Please refresh the page and try again.');
        }
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;
        
        // Display user message
        this.addUserMessage(message);
        this.messageInput.value = '';
        this.autoResizeTextarea();
        
        // Disable input
        this.disableInput();
        
        // Show typing indicator
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
            // Prepare SSE request
            const formData = new FormData();
            formData.append('session_id', this.sessionId);
            formData.append('message', message);
            formData.append('step', this.currentStep);
            
            // Create empty AI message bubble
            this.hideTypingIndicator();
            this.currentMessageBubble = this.createEmptyBotMessage();
            
            // Establish SSE connection
            const response = await fetch('/chat/message/stream', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Stream request failed');
            }
            
            // Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // Process complete SSE messages
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete part
                
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
            this.addBotMessage('❌ Sorry, network connection issue. Please try again.');
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
            
            // Hide typing indicator
            this.hideTypingIndicator();
            
            if (data.status === 'success') {
                // Display AI reply
                this.addBotMessage(data.message);
                
                // Update session state
                this.currentStep = data.step;
                
                // Check if file upload is needed
                if (data.need_files) {
                    this.showFileUploadPrompt();
                }
                
                // Check if completed
                if (data.completed) {
                    this.handleCompletion(data);
                }
                
                // If in requirement confirmation stage, continue to enable input
                if (this.currentStep === 'requirement_confirmation') {
                    this.enableInput();
                } else if (this.currentStep === 'file_upload') {
                    // Disable text input during file upload stage
                    this.disableInput();
                }
                
            } else {
                this.addBotMessage('Sorry, an error occurred while processing your message. Please try again.');
            }
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.hideTypingIndicator();
            this.addBotMessage('Sorry, network connection issue. Please try again.');
            this.enableInput();
        }
    }
    
    async handleStreamChunk(data) {
        if (data.type === 'content') {
            // Append content to current message
            this.appendToCurrentMessage(data.content);
            
        } else if (data.type === 'progress') {
            // Handle progress updates
            this.updateProgressUI(data);
            
        } else if (data.type === 'complete') {
            // Handle completion state
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
            // Continue conversation
            this.currentStep = data.step || 'requirement_confirmation';
            this.finalizeCurrentMessage();
            this.enableInput();
            
        } else if (data.type === 'error') {
            // Error handling
            this.finalizeCurrentMessage();
            this.hideProgressUI();
            this.addBotMessage('❌ ' + data.message);
            this.enableInput();
            
        } else if (data.type === 'heartbeat') {
            // Heartbeat message, keep connection alive
            // No special handling needed, just keep connection active
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
        bubble.innerHTML = '<span class="cursor">▎</span>'; // Cursor effect
        
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
                // Insert content before cursor
                cursor.insertAdjacentHTML('beforebegin', content);
            } else {
                // If no cursor, append directly
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
                cursor.remove(); // Remove cursor
            }
            
            // Handle Markdown formatting
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
        
        // Handle message content (supports simple HTML)
        if (typeof content === 'string') {
            // Simple Markdown support
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
        this.addBotMessage('Now please upload candidate resume files. You can click the 📎 button below or drag files directly here.');
        this.showFileUpload();
    }
    
    async uploadFiles() {
        const files = this.resumeFiles.files;
        if (!files || files.length === 0) {
            alert('Please select files to upload first');
            return;
        }
        
        const formData = new FormData();
        formData.append('session_id', this.sessionId);
        
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }
        
        try {
            this.uploadBtn.disabled = true;
            this.uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            
            this.addBotMessage(`📤 Uploading ${files.length} files...`);
            this.hideFileUpload();
            
            // Use streaming upload endpoint
            const response = await fetch('/chat/upload/stream', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Stream request failed');
            }
            
            this.addBotMessage(`✅ File upload successful, processing started...`);
            
            // Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // Process complete SSE messages
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete part
                
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
            this.addBotMessage('❌ File upload failed, please try again.');
        } finally {
            this.uploadBtn.disabled = false;
            this.uploadBtn.innerHTML = '<i class="fas fa-upload"></i> Upload Files';
        }
    }
    
    async startProcessing(taskId) {
        this.addBotMessage('🔄 Processing your resumes, please wait...');
        this.statusBadge.textContent = 'Processing';
        this.statusBadge.className = 'badge bg-warning ms-2';
        
        // Poll processing status
        const pollStatus = async () => {
            try {
                const response = await fetch(`/chat/status/${taskId}`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    this.addBotMessage('✅ Processing completed! Generating evaluation report...');
                    this.statusBadge.textContent = 'Completed';
                    this.statusBadge.className = 'badge bg-success ms-2';
                    
                    // Display report content
                    this.showReport(data.result);
                    
                } else if (data.status === 'failed') {
                    this.addBotMessage('❌ Processing failed: ' + data.error);
                    this.statusBadge.textContent = 'Failed';
                    this.statusBadge.className = 'badge bg-danger ms-2';
                    
                } else {
                    // Continue polling
                    setTimeout(pollStatus, 2000);
                }
                
            } catch (error) {
                console.error('Status check failed:', error);
                this.addBotMessage('❌ Status check failed, please refresh the page and try again.');
                this.statusBadge.textContent = 'Error';
                this.statusBadge.className = 'badge bg-danger ms-2';
            }
        };
        
        pollStatus();
    }
    
    handleCompletion(data) {
        if (data.result_url) {
            this.addBotMessage('🎉 Resume screening completed! Redirecting to results page...');
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
        // Display report completion message
        this.addBotMessage('📊 Evaluation report generated successfully! Here are the detailed results:');
        
        // Create report display area
        const reportMessage = this.createReportMessage(result.report);
        this.chatMessages.appendChild(reportMessage);
        this.scrollToBottom();
        
        // Disable input, processing completed
        this.disableInput();
        
        // Add action buttons
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
                        <i class="fas fa-file-alt"></i> Candidate Evaluation Report
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
        if (!markdown) return '<p>Report content is not available</p>';
        
        // Simple Markdown to HTML conversion
        let html = markdown
            // Title processing
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            // Bold and italic
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Line break processing
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        
        // Process tables
        html = this.convertMarkdownTable(html);
        
        // Wrap paragraphs
        if (!html.includes('<p>') && !html.includes('<h1>') && !html.includes('<h2>') && !html.includes('<h3>')) {
            html = '<p>' + html + '</p>';
        }
        
        return html;
    }
    
    convertMarkdownTable(html) {
        // Find table rows
        const tableRegex = /(\|[^|\n]*\|[^|\n]*\|[^\n]*\n)+/g;
        
        return html.replace(tableRegex, (match) => {
            const rows = match.trim().split('\n');
            if (rows.length < 2) return match;
            
            let tableHtml = '<table class="table table-striped table-bordered table-sm">';
            
            // Process table header
            const headerRow = rows[0];
            const headers = headerRow.split('|').map(h => h.trim()).filter(h => h);
            
            tableHtml += '<thead><tr>';
            headers.forEach(header => {
                tableHtml += `<th>${header}</th>`;
            });
            tableHtml += '</tr></thead>';
            
            // Skip separator row, process data rows
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
                    <i class="fas fa-print"></i> Print Report
                </button>
                <button class="btn btn-success btn-sm" onclick="this.downloadReport()">
                    <i class="fas fa-download"></i> Download Report
                </button>
                <button class="btn btn-info btn-sm" onclick="location.reload()">
                    <i class="fas fa-refresh"></i> Restart
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
        
        // Create or update progress container
        let progressContainer = document.getElementById('progress-container');
        if (!progressContainer) {
            progressContainer = this.createProgressContainer();
        }
        
        // Update progress bar
        const progressBar = progressContainer.querySelector('.progress-bar');
        const progressText = progressContainer.querySelector('.progress-text');
        const progressMessage = progressContainer.querySelector('.progress-message');
        const progressDetail = progressContainer.querySelector('.progress-detail');
        
        // Update progress bar
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        
        // Update text
        progressText.textContent = `${Math.round(progress)}%`;
        progressMessage.textContent = message;
        
        // Update detailed information
        if (total_items && completed_items !== undefined) {
            progressDetail.textContent = `${completed_items}/${total_items}`;
            progressDetail.style.display = 'block';
        } else if (current_item) {
            progressDetail.textContent = current_item;
            progressDetail.style.display = 'block';
        } else {
            progressDetail.style.display = 'none';
        }
        
        // Update stage styles
        this.updateStageIndicator(stage);
    }

    createProgressContainer() {
        const progressContainer = document.createElement('div');
        progressContainer.id = 'progress-container';
        progressContainer.className = 'progress-container';
        
        progressContainer.innerHTML = `
            <div class="progress-header">
                <span class="progress-title">Processing Progress</span>
                <span class="progress-text">0%</span>
            </div>
            <div class="progress-bar-container">
                <div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div class="progress-info">
                <div class="progress-message">Initializing...</div>
                <div class="progress-detail" style="display: none;"></div>
            </div>
            <div class="progress-stages">
                <div class="stage-indicator" data-stage="initialization">Initialization</div>
                <div class="stage-indicator" data-stage="resume_processing">Resume Processing</div>
                <div class="stage-indicator" data-stage="dimension_generation">Dimension Generation</div>
                <div class="stage-indicator" data-stage="candidate_evaluation">Candidate Evaluation</div>
                <div class="stage-indicator" data-stage="report_generation">Report Generation</div>
            </div>
        `;
        
        // Insert into chat message area
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
        // Hide progress UI
        this.hideProgressUI();
        
        // Display result summary
        const resultSummary = `
            ✅ **Processing Completed**
            
            📊 **Evaluation Result Summary**
            - Number of candidates: ${result.evaluations ? result.evaluations.length : 0}
            - Generated at: ${new Date().toLocaleString()}
            
            📝 Here is the detailed evaluation report:
        `;
        
        this.addBotMessage(resultSummary);
        
        // Display report content directly instead of showing buttons
        if (result.report) {
            this.showReportContent(result.report);
        }
        
        // Add action buttons
        this.addDownloadButton(result);
    }

    showReportContent(reportContent) {
        // Display report content directly in chat window
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
        
        // Print button
        const printBtn = document.createElement('button');
        printBtn.className = 'btn btn-primary btn-sm';
        printBtn.innerHTML = '<i class="fas fa-print"></i> Print Report';
        printBtn.onclick = () => window.print();
        
        // Download button
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'btn btn-success btn-sm';
        downloadBtn.innerHTML = '<i class="fas fa-download"></i> Download Report';
        downloadBtn.onclick = () => this.downloadReportContent(result.report || '');
        
        // Restart button
        const restartBtn = document.createElement('button');
        restartBtn.className = 'btn btn-info btn-sm';
        restartBtn.innerHTML = '<i class="fas fa-refresh"></i> Restart';
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
            alert('Report content is not available');
            return;
        }
        
        // Create download link
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

// Initialize chatbot
document.addEventListener('DOMContentLoaded', () => {
    new ChatBot();
});