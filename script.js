document.addEventListener('DOMContentLoaded', () => {
    // Basic interaction script for the Perplexity Clone UI
    
    // Auto-resize for textarea in search box
    const searchInput = document.querySelector('.search-input-wrapper textarea');
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            this.style.height = 'auto'; // Reset the height
            this.style.height = (this.scrollHeight) + 'px'; // Set it to the scroll height
        });
        
        // Focus state effect on container
        const searchContainer = document.querySelector('.search-container');
        searchInput.addEventListener('focus', () => {
            searchContainer.style.borderColor = 'var(--border-light)';
        });
        
        searchInput.addEventListener('blur', () => {
            searchContainer.style.borderColor = 'var(--border-color)';
        });
    }

    // Interactive chips
    const chips = document.querySelectorAll('.chip');
    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            // Remove active class from all
            chips.forEach(c => c.classList.remove('active'));
            // Add active class to clicked
            chip.classList.add('active');
        });
    });

    const submitBtn = document.querySelector('.submit-btn');
    const chatFeed = document.getElementById('chat-feed');
    const suggestionsContainer = document.querySelector('.suggestions-container');
    const logo = document.querySelector('.logo');
    
    // File Upload Elements
    const pdfUploadInput = document.getElementById('pdf-upload');
    const attachBtn = document.querySelector('.attach-btn');
    const fileIndicator = document.getElementById('file-attachment-indicator');
    const attachedFilename = document.getElementById('attached-filename');
    const resetBtn = document.getElementById('reset-btn');
    const newThreadBtn = document.getElementById('new-thread-btn');

    let lastQuery = "";

    // Reset Functionality
    async function resetChat() {
        try {
            await fetch('http://localhost:5001/api/reset', { method: 'POST' });
            
            // Clear UI
            chatFeed.innerHTML = '';
            chatFeed.classList.add('chat-feed-hidden');
            suggestionsContainer.style.display = 'block';
            logo.classList.remove('shrunk');
            
            // Clear File indicator
            fileIndicator.classList.add('file-attachment-hidden');
            attachedFilename.textContent = '';
            
            console.log("Chat and RAG memory reset successfully.");
        } catch (error) {
            console.error("Reset error:", error);
        }
    }

    if (resetBtn) resetBtn.addEventListener('click', resetChat);
    if (newThreadBtn) newThreadBtn.addEventListener('click', resetChat);

    // PDF Upload Handler
    if (pdfUploadInput) {
        pdfUploadInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            // UI Loading state
            if (attachBtn) attachBtn.classList.add('uploading');
            if (fileIndicator) fileIndicator.classList.remove('file-attachment-hidden');
            if (attachedFilename) attachedFilename.textContent = file.name + " (Reading Document...)";

            const formData = new FormData();
            formData.append('pdf', file);

            try {
                const response = await fetch('http://localhost:5001/api/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                
                if (response.ok) {
                    attachedFilename.textContent = file.name + " (Ready)";
                } else {
                    attachedFilename.textContent = "Failed: " + data.error;
                }
            } catch (error) {
                console.error("Upload error:", error);
                attachedFilename.textContent = "Error: " + error.message;
            } finally {
                if (attachBtn) attachBtn.classList.remove('uploading');
                pdfUploadInput.value = ''; // Reset input
            }
        });
    }

    function handleSearch() {
        const query = searchInput.value.trim() || lastQuery;
        if (!query) return;
        
        lastQuery = query;

        // Clear input box immediately
        searchInput.value = '';
        searchInput.style.height = 'auto';

        // Prepare UI
        chatFeed.classList.remove('chat-feed-hidden');
        suggestionsContainer.style.display = 'none';
        logo.classList.add('shrunk');

        // Create User Message Bubble
        const userDiv = document.createElement('div');
        userDiv.className = 'user-message';
        userDiv.textContent = query;
        
        // Create AI Loading Bubble
        const aiDiv = document.createElement('div');
        aiDiv.className = 'ai-message';
        aiDiv.innerHTML = `
            <div class="message-header"><i class="fa-solid fa-sparkles"></i> Answer</div>
            <div class="message-content">Thinking...</div>
        `;

        // Append both and scroll down
        chatFeed.appendChild(userDiv);
        chatFeed.appendChild(aiDiv);
        chatFeed.scrollTo(0, chatFeed.scrollHeight);

        // Show loading state on form
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        submitBtn.disabled = true;

        const aiContent = aiDiv.querySelector('.message-content');

        // Send request to Flask backend with a a 15-second timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        fetch('http://localhost:5001/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: query }),
            signal: controller.signal
        })
        .then(async response => {
            clearTimeout(timeoutId);
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || 'Server error: ' + response.status);
            }
            
            // Access the response stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let isFirstChunk = true;
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }
                
                const chunkText = decoder.decode(value, { stream: true });
                
                // --- ERROR DETECTION IN STREAM ---
                if (chunkText.includes("[ERROR_429]")) {
                    showRetryError(aiContent, aiDiv, "API Rate Limit reached. Please wait 60 seconds.");
                    return; // Stop stream processing
                }
                if (chunkText.includes("[ERROR_GENERIC]")) {
                    aiContent.innerHTML = `<span style="color: #ff6b6b;"><strong>Server Error:</strong> ${chunkText.replace('[ERROR_GENERIC]: ', '')}</span>`;
                    return;
                }

                if (isFirstChunk) {
                    aiContent.textContent = ''; // Clear 'Thinking...'
                    isFirstChunk = false;
                }
                
                aiContent.textContent += chunkText;
                chatFeed.scrollTo(0, chatFeed.scrollHeight);
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            console.error('Fetch Error:', error);
            let errorMsg = error.message;
            if (error.name === 'AbortError') {
                errorMsg = "Request timed out. The AI is slow right now. Please try again or refresh!";
            }
            
            const resCode = errorMsg.includes("429") || errorMsg.includes("RESOURCE_EXHAUSTED");
            
            if (resCode) {
                showRetryError(aiContent, aiDiv, "API Rate Limit reached. Please wait 60 seconds.");
            } else {
                aiContent.innerHTML = `<span style="color: #ff6b6b;"><strong>Error:</strong> ${errorMsg}</span>`;
            }
            chatFeed.scrollTo(0, chatFeed.scrollHeight);
        })
        .finally(() => {
            submitBtn.innerHTML = '<i class="fa-solid fa-bars-staggered"></i>';
            submitBtn.disabled = false;
        });

        // Helper to show the retry button and countdown
        function showRetryError(contentElem, parentElem, msg) {
            contentElem.innerHTML = `
                <span style="color: #ff6b6b;"><strong>System Notice:</strong> ${msg}</span><br>
                <button class="retry-btn" id="retry-btn">Try Again Now</button>
                <p id="retry-timer" style="font-size: 12px; margin-top: 5px; color: var(--text-secondary);"></p>
            `;
            
            const retryBtn = parentElem.querySelector('#retry-btn');
            const retryTimer = parentElem.querySelector('#retry-timer');
            
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    retryBtn.disabled = true;
                    let count = 5;
                    const interval = setInterval(() => {
                        retryTimer.textContent = `Retrying in ${count}s...`;
                        if (count <= 0) {
                            clearInterval(interval);
                            handleSearch(); // Auto-retry
                        }
                        count--;
                    }, 1000);
                });
            }
        }
    }

    // Trigger on button click
    if (submitBtn) {
        submitBtn.addEventListener('click', handleSearch);
    }

    // Trigger on Enter key (without Shift)
    if (searchInput) {
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
            }
        });
    }
});
