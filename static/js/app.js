// Paramedic Voice Assistant - Frontend JavaScript
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const chatArea = document.getElementById('chatArea');
    const inputForm = document.getElementById('inputForm');
    const textInput = document.getElementById('textInput');
    const micBtn = document.getElementById('micBtn');
    const micIcon = micBtn.querySelector('.mic-icon');
    const stopIcon = micBtn.querySelector('.stop-icon');
    const avatar = document.getElementById('avatar');
    const pulseRing = document.getElementById('pulseRing');
    const avatarBtn = document.getElementById('avatarBtn');
    
    // Modals
    const previewModal = document.getElementById('previewModal');
    const successModal = document.getElementById('successModal');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const modalTitle = document.getElementById('modalTitle');
    const modalSubtitle = document.getElementById('modalSubtitle');
    const modalBody = document.getElementById('modalBody');
    const tryAgainBtn = document.getElementById('tryAgainBtn');
    const printBtn = document.getElementById('printBtn');
    const submitBtn = document.getElementById('submitBtn');
    const closeSuccessBtn = document.getElementById('closeSuccessBtn');
    const successMessage = document.getElementById('successMessage');

    // State
    let isListening = false;
    let mediaRecorder = null;
    let audioChunks = [];
    let currentReportType = null;
    let currentReportData = null;
    let hasStarted = false;

    // Check if microphone is available
    async function checkMicrophonePermission() {
        try {
            // Check if mediaDevices is supported
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.error('MediaDevices API not supported');
                return 'unsupported';
            }
            
            // Check current permission status if available
            if (navigator.permissions && navigator.permissions.query) {
                const result = await navigator.permissions.query({ name: 'microphone' });
                return result.state; // 'granted', 'denied', or 'prompt'
            }
            
            return 'prompt'; // Default to prompt if we can't check
        } catch (error) {
            console.log('Permission check not available:', error);
            return 'prompt';
        }
    }

    // Initialize MediaRecorder for audio recording
    async function initMediaRecorder() {
        try {
            // Check if mediaDevices is supported
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                addMessage('system', '⚠️ Your browser does not support audio recording. Please use Chrome, Firefox, or Edge.');
                return false;
            }
            
            addMessage('system', '🎤 Requesting microphone access...');
            
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 44100
                }
            });
            
            // Remove the "requesting" message
            const lastSystem = chatArea.querySelector('.message.system:last-child');
            if (lastSystem && lastSystem.textContent.includes('Requesting')) {
                lastSystem.remove();
            }
            
            // Check for supported MIME types
            let mimeType = 'audio/webm';
            if (!MediaRecorder.isTypeSupported('audio/webm')) {
                if (MediaRecorder.isTypeSupported('audio/mp4')) {
                    mimeType = 'audio/mp4';
                } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
                    mimeType = 'audio/ogg';
                }
            }
            
            mediaRecorder = new MediaRecorder(stream, { mimeType });
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: mimeType });
                audioChunks = [];
                await sendAudioForTranscription(audioBlob);
            };

            console.log('MediaRecorder initialized successfully with', mimeType);
            addMessage('system', '✅ Microphone ready!');
            
            // Remove the success message after 2 seconds
            setTimeout(() => {
                const successMsg = chatArea.querySelector('.message.system:last-child');
                if (successMsg && successMsg.textContent.includes('Microphone ready')) {
                    successMsg.remove();
                }
            }, 2000);
            
            return true;
        } catch (error) {
            console.error('Microphone access error:', error);
            
            // Remove any pending messages
            const pendingMsg = chatArea.querySelector('.message.system:last-child');
            if (pendingMsg && pendingMsg.textContent.includes('Requesting')) {
                pendingMsg.remove();
            }
            
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                addMessage('system', '❌ Microphone access denied. Click the lock icon in the address bar to allow microphone access, then refresh the page.');
            } else if (error.name === 'NotFoundError') {
                addMessage('system', '❌ No microphone found. Please connect a microphone and refresh.');
            } else if (error.name === 'NotReadableError') {
                addMessage('system', '❌ Microphone is in use by another application. Please close other apps using the mic.');
            } else {
                addMessage('system', `❌ Microphone error: ${error.message}. Try refreshing the page.`);
            }
            return false;
        }
    }

    // Send audio to backend for transcription
    async function sendAudioForTranscription(audioBlob) {
        showLoading();
        addMessage('system', 'Transcribing...');

        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');

            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            hideLoading();

            // Remove the "Transcribing..." message
            const lastSystem = chatArea.querySelector('.message.system:last-child');
            if (lastSystem && lastSystem.textContent === 'Transcribing...') {
                lastSystem.remove();
            }

            if (result.error) {
                addMessage('ai', `Sorry, transcription failed: ${result.error}`);
                return;
            }

            if (result.transcription) {
                // Process the transcribed text
                processMessage(result.transcription);
            } else {
                addMessage('ai', "I didn't catch that. Could you try again?");
            }
        } catch (error) {
            hideLoading();
            console.error('Transcription error:', error);
            addMessage('ai', "Sorry, there was an error processing your voice. Please try again.");
        }
    }

    // Start greeting
    function startConversation() {
        if (!hasStarted) {
            hasStarted = true;
            clearWelcome();
            addMessage('ai', "Hello! I'm your Paramedic Assistant. I can help with schedule queries, shift changes, your daily checklist, or incident reports. What do you need?");
            speakText("Hello! I'm your Paramedic Assistant. How can I help you today?");
        }
    }

    // Event Listeners
    avatarBtn.addEventListener('click', async () => {
        startConversation();
        if (!isListening) {
            await startListening();
        }
    });

    micBtn.addEventListener('click', async () => {
        if (!hasStarted) startConversation();
        if (isListening) {
            stopListening();
        } else {
            await startListening();
        }
    });

    inputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = textInput.value.trim();
        if (!message) return;
        
        if (!hasStarted) startConversation();
        clearWelcome();
        textInput.value = '';
        processMessage(message);
    });

    tryAgainBtn.addEventListener('click', () => {
        closeModal(previewModal);
        resetSession(currentReportType);
        addMessage('ai', "No problem! Let's start over. What would you like to do?");
    });

    printBtn.addEventListener('click', () => {
        printReport();
    });

    submitBtn.addEventListener('click', () => {
        submitReport();
    });

    closeSuccessBtn.addEventListener('click', () => {
        closeModal(successModal);
    });

    // Audio Recording Functions
    async function startListening() {
        // Initialize MediaRecorder if not already done
        if (!mediaRecorder) {
            const success = await initMediaRecorder();
            if (!success) return;
        }
        
        isListening = true;
        audioChunks = [];
        micBtn.classList.add('listening');
        avatar.classList.add('listening');
        pulseRing.classList.add('active');
        micIcon.style.display = 'none';
        stopIcon.style.display = 'block';
        
        mediaRecorder.start();
        console.log('Recording started');
    }

    function stopListening() {
        isListening = false;
        micBtn.classList.remove('listening');
        avatar.classList.remove('listening');
        pulseRing.classList.remove('active');
        micIcon.style.display = 'block';
        stopIcon.style.display = 'none';
        
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            console.log('Recording stopped');
        }
    }

    // Message Processing
    async function processMessage(message) {
        addMessage('user', message);
        showLoading();

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            const result = await response.json();
            hideLoading();

            if (result.error) {
                addMessage('ai', `Sorry, something went wrong: ${result.error}`);
                return;
            }

            // Add AI response
            addMessage('ai', result.response);
            
            // Speak the response
            speakText(result.response);

            // Show preview modal if ready
            if (result.show_preview && result.data) {
                currentReportType = result.type;
                currentReportData = result.data;
                showPreviewModal(result.type, result.data);
            }

        } catch (error) {
            hideLoading();
            console.error('Error:', error);
            addMessage('ai', "Sorry, I couldn't process that. Please try again.");
        }
    }

    // Chat UI Functions
    function addMessage(type, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${type}`;
        msgDiv.textContent = text;
        chatArea.appendChild(msgDiv);
        scrollToBottom();
    }

    function clearWelcome() {
        const welcome = chatArea.querySelector('.chat-welcome');
        if (welcome) welcome.remove();
    }

    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    // Text to Speech
    async function speakText(text) {
        try {
            const response = await fetch('/api/speak', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });

            if (response.ok) {
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);
                audio.play();
            }
        } catch (error) {
            console.error('TTS error:', error);
        }
    }

    // Loading State
    function showLoading() {
        loadingOverlay.classList.add('active');
    }

    function hideLoading() {
        loadingOverlay.classList.remove('active');
    }

    // Modal Functions
    function openModal(modal) {
        modal.classList.add('active');
    }

    function closeModal(modal) {
        modal.classList.remove('active');
    }

    function showPreviewModal(type, data) {
        let title = 'Review Report';
        let content = '';

        switch (type) {
            case 'shift_change':
                title = 'Shift Change Request';
                content = buildFormPreview(data.collected, [
                    { key: 'first_name', label: 'First Name' },
                    { key: 'last_name', label: 'Last Name' },
                    { key: 'medic_number', label: 'Medic Number' },
                    { key: 'shift_day', label: 'Shift Day' },
                    { key: 'shift_start', label: 'Shift Start' },
                    { key: 'shift_end', label: 'Shift End' },
                    { key: 'requested_action', label: 'Requested Action' }
                ]);
                break;

            case 'checklist':
                title = 'Paramedic Checklist';
                content = buildChecklistTable(data.completed, data.issues);
                break;

            case 'form':
                title = data.form_name || 'Form';
                content = buildFormPreview(data.collected);
                break;

            default:
                content = '<p>No data available</p>';
        }

        modalTitle.textContent = title;
        modalBody.innerHTML = content;
        openModal(previewModal);
    }

    function buildFormPreview(data, fields = null) {
        let html = '<div class="form-preview">';
        
        if (fields) {
            fields.forEach(field => {
                const value = data[field.key] || '';
                html += `
                    <div class="form-field">
                        <span class="field-label">${field.label}</span>
                        <span class="field-value ${!value ? 'empty' : ''}">${value || 'Pending entry...'}</span>
                    </div>
                `;
            });
        } else {
            for (const [key, value] of Object.entries(data)) {
                const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                html += `
                    <div class="form-field">
                        <span class="field-label">${label}</span>
                        <span class="field-value ${!value ? 'empty' : ''}">${value || 'Pending entry...'}</span>
                    </div>
                `;
            }
        }
        
        html += '</div>';
        return html;
    }

    function buildChecklistTable(completed, issues) {
        const items = [
            { code: 'ACRc', type: 'ACR Completion', desc: 'ACRs/PCRs unfinished' },
            { code: 'ACEr', type: 'ACE Response', desc: 'ACE reviews requiring comment' },
            { code: 'CERT-DL', type: 'Drivers License', desc: 'License validity' },
            { code: 'CERT-Va', type: 'Vaccinations', desc: 'Vaccinations up to date' },
            { code: 'CERT-CE', type: 'Education', desc: 'Continuous Education' },
            { code: 'UNIF', type: 'Uniform', desc: 'Uniform credits' },
            { code: 'CRIM', type: 'CRC', desc: 'Criminal Record Check' },
            { code: 'ACP', type: 'ACP Status', desc: 'ACP Certification' },
            { code: 'VAC', type: 'Vacation', desc: 'Vacation approved' },
            { code: 'MEALS', type: 'Missed Meals', desc: 'Meal claims outstanding' },
            { code: 'OVER', type: 'Overtime', desc: 'Overtime requests' }
        ];

        let html = '<table class="report-table"><thead><tr>';
        html += '<th>Item</th><th>Type</th><th>Status</th><th>Issues</th>';
        html += '</tr></thead><tbody>';

        items.forEach(item => {
            const status = completed[item.code] || { status: 'pending', issues: 0 };
            const statusClass = status.status === 'good' ? 'good' : 
                               status.status === 'bad' ? 'bad' : 'pending';
            const statusText = status.status ? status.status.toUpperCase() : 'PENDING';
            
            html += `<tr>
                <td style="font-weight:700;color:#1e40af">${item.code}</td>
                <td>${item.type}</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td style="text-align:center">${status.issues || 0}</td>
            </tr>`;
        });

        html += '</tbody></table>';
        return html;
    }

    // Report Actions
    async function submitReport() {
        if (!currentReportType || !currentReportData) return;

        showLoading();
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending...';

        let endpoint = '/api/submit/form';
        let body = { data: currentReportData.collected || currentReportData };

        switch (currentReportType) {
            case 'shift_change':
                endpoint = '/api/submit/shift-change';
                body = {};
                break;
            case 'checklist':
                endpoint = '/api/submit/checklist';
                body = {};
                break;
            case 'form':
                body.form_name = currentReportData.form_name || 'Form';
                break;
        }

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const result = await response.json();
            hideLoading();
            closeModal(previewModal);

            if (result.success) {
                successMessage.textContent = result.message;
                openModal(successModal);
                addMessage('system', result.message);
            } else {
                addMessage('ai', `Submission failed: ${result.message}`);
            }

        } catch (error) {
            hideLoading();
            console.error('Submit error:', error);
            addMessage('ai', 'Failed to submit. Please try again.');
        }

        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit';
        currentReportType = null;
        currentReportData = null;
    }

    function printReport() {
        const printContent = modalBody.innerHTML;
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>${modalTitle.textContent}</title>
                <style>
                    body { font-family: Arial, sans-serif; padding: 20px; }
                    h1 { color: #1e40af; margin-bottom: 5px; }
                    p { color: #666; margin-bottom: 20px; }
                    table { width: 100%; border-collapse: collapse; }
                    th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background: #f1f5f9; font-size: 11px; text-transform: uppercase; }
                    .field-label { font-size: 11px; color: #666; text-transform: uppercase; }
                    .field-value { font-size: 14px; margin-top: 4px; }
                    .form-field { padding: 10px 0; border-bottom: 1px solid #eee; }
                    .status-badge { padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: bold; }
                    .status-badge.good { background: #dcfce7; color: #16a34a; }
                    .status-badge.bad { background: #fee2e2; color: #dc2626; }
                    .status-badge.pending { background: #f1f5f9; color: #64748b; }
                </style>
            </head>
            <body>
                <h1>${modalTitle.textContent}</h1>
                <p>EffectiveAI Paramedic Services - ${new Date().toLocaleDateString()}</p>
                ${printContent}
            </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.print();
    }

    async function resetSession(type) {
        try {
            await fetch('/api/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type || 'all' })
            });
        } catch (error) {
            console.error('Reset error:', error);
        }
    }
});
