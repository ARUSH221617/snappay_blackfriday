document.addEventListener('DOMContentLoaded', () => {
    const statusText = document.getElementById('status-text');
    const startBtn = document.getElementById('start-btn');
    const inputArea = document.getElementById('input-area');
    const inputPrompt = document.getElementById('input-prompt');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const logContainer = document.getElementById('log-container');
    const autoScrollToggle = document.getElementById('auto-scroll');

    let isAutoScroll = true;

    // --- State Management ---
    function updateStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                // Update Status Badge
                if (data.running) {
                    statusText.textContent = "Running";
                    statusText.className = "status-badge status-running";
                    startBtn.disabled = true;
                    startBtn.textContent = "Bot Running";
                } else {
                    statusText.textContent = "Stopped";
                    statusText.className = "status-badge status-stopped";
                    startBtn.disabled = false;
                    startBtn.textContent = "Start Bot";
                }

                // Update Input Area
                if (data.waiting_for_input) {
                    inputArea.classList.add('active');
                    inputPrompt.textContent = data.input_prompt || "Bot needs input:";

                    // Auto-focus input if not already focused
                    if (document.activeElement !== userInput) {
                        userInput.focus();
                    }

                    // Update Status to Waiting if running
                    if (data.running) {
                         statusText.textContent = "Waiting for Input";
                         statusText.className = "status-badge status-waiting";
                    }
                } else {
                    inputArea.classList.remove('active');
                }
            })
            .catch(err => {
                console.error("Status fetch error:", err);
                statusText.textContent = "Connection Lost";
                statusText.className = "status-badge status-stopped";
            });
    }

    // --- Log Management ---
    let seenLogs = 0; // Simple tracker, ideally backend sends IDs or we just append new ones
    // Since backend sends ALL logs every time, we need to clear and re-render or be smart.
    // The current backend implementation: `return jsonify({"logs": bot_manager.get_logs()})`
    // Looking at app.py, `get_logs` empties the queue:
    // while not self.log_queue.empty(): logs.append(self.log_queue.get())
    // Wait, `get_logs` empties the queue?
    // Let's re-read app.py carefully.

    /*
    def get_logs(self):
        logs = []
        while not self.log_queue.empty():
            logs.append(self.log_queue.get())
        return logs
    */

    // YES. It drains the queue. So subsequent calls only return NEW logs.
    // This makes appending easy.

    function fetchLogs() {
        fetch('/api/logs')
            .then(r => r.json())
            .then(data => {
                if (data.logs && data.logs.length > 0) {
                    data.logs.forEach(logMsg => {
                        const div = document.createElement('div');
                        div.className = 'log-entry';

                        // Simple styling heuristics
                        const lowerLog = logMsg.toLowerCase();
                        if (lowerLog.includes('error') || lowerLog.includes('exception') || lowerLog.includes('critical')) {
                            div.classList.add('log-error');
                        } else if (lowerLog.includes('warning')) {
                            div.classList.add('log-warning');
                        } else if (lowerLog.includes('input')) {
                            div.classList.add('log-input');
                        } else {
                            div.classList.add('log-info');
                        }

                        // Timestamp could be added here if backend doesn't provide it
                        // div.textContent = `[${new Date().toLocaleTimeString()}] ${logMsg}`;
                        div.textContent = logMsg;

                        logContainer.appendChild(div);
                    });

                    if (isAutoScroll) {
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                }
            })
            .catch(err => console.error("Log fetch error:", err));
    }

    // --- Interaction Handlers ---
    startBtn.addEventListener('click', () => {
        fetch('/api/start', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                console.log("Start response:", data);
                updateStatus();
            })
            .catch(err => alert("Failed to start bot: " + err));
    });

    function sendInput() {
        const val = userInput.value;
        if (!val) return; // Don't send empty? Maybe user wants to.

        fetch('/api/input', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: val })
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === "input_sent") {
                userInput.value = '';
                updateStatus();
            } else {
                alert("Error sending input: " + data.status);
            }
        })
        .catch(err => alert("Failed to send input: " + err));
    }

    sendBtn.addEventListener('click', sendInput);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendInput();
        }
    });

    // Auto-scroll logic
    // Detect if user scrolls up, disable auto-scroll.
    logContainer.addEventListener('scroll', () => {
        // If scrolled to bottom (with some tolerance)
        const isAtBottom = logContainer.scrollHeight - logContainer.scrollTop <= logContainer.clientHeight + 50;
        isAutoScroll = isAtBottom;

        // Update toggle checkbox if we have one (optional UI enhancement)
        if (autoScrollToggle) {
            autoScrollToggle.checked = isAutoScroll;
        }
    });

    if (autoScrollToggle) {
        autoScrollToggle.addEventListener('change', (e) => {
            isAutoScroll = e.target.checked;
            if (isAutoScroll) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        });
    }

    // --- Polling ---
    setInterval(updateStatus, 1000);
    setInterval(fetchLogs, 1000); // 1s polling for logs is reasonable

    // Initial call
    updateStatus();
});
