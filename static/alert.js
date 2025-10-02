// Flash Message System
        const flashContainer = document.getElementById('flash-container');
        let messageCount = 0;
        let currentTheme = 'indigo';
        let animationSpeed = 500;
        let defaultDuration = 5;
        let currentStyle = 'default';
        let showProgress = true;
        let showClose = true;
        let pauseOnHover = true;
        
        // Flash Message Function
        function flashMessage(options) {
            const {
                type = 'info',
                title = '',
                message = '',
                duration = defaultDuration * 1000,
                position = 'top-right'
            } = options;
            
            // Create message element
            const messageId = `flash-${Date.now()}-${messageCount++}`;
            const messageEl = document.createElement('div');
            messageEl.id = messageId;
            messageEl.className = `flash-message ${currentStyle}`;
            
            // Set position
            updateContainerPosition(position);
            
            // Set colors based on type and theme
            const colors = getColors(type);
            
            // Create message content
            let messageHTML = `
                <div class="flash-content" style="background-color: ${colors.bg};">
                    <div class="flash-icon" style="background-color: ${colors.iconBg};">
                        ${getIcon(type)}
                    </div>
                    <div class="flash-text">
                        ${title ? `<h4 class="font-medium text-sm" style="color: ${colors.title};">${title}</h4>` : ''}
                        <p class="text-sm" style="color: ${colors.text};">${message}</p>
                    </div>
                    ${showClose ? `
                    <button class="flash-close ml-4" onclick="closeMessage('${messageId}')">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" style="color: ${colors.close};" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
                        </svg>
                    </button>
                    ` : ''}
                </div>
                ${showProgress ? `
                <div class="flash-progress" style="background-color: ${colors.progressBg};">
                    <div class="progress-bar" style="width: 100%; height: 100%; background-color: ${colors.progress};"></div>
                </div>
                ` : ''}
            `;
            
            messageEl.innerHTML = messageHTML;
            
            // Add to container
            flashContainer.appendChild(messageEl);
            
            // Show message with animation
            setTimeout(() => {
                messageEl.classList.add('show');
            }, 10);
            
            // Set up progress bar animation
            if (showProgress) {
                const progressBar = messageEl.querySelector('.progress-bar');
                progressBar.style.transition = `width ${duration}ms linear`;
                
                setTimeout(() => {
                    progressBar.style.width = '0%';
                }, 10);
            }
            
            // Set up auto-dismiss
            let dismissTimeout;
            
            const startDismissTimer = () => {
                dismissTimeout = setTimeout(() => {
                    closeMessage(messageId);
                }, duration);
            };
            
            startDismissTimer();
            
            // Pause on hover if enabled
            if (pauseOnHover) {
                messageEl.addEventListener('mouseenter', () => {
                    clearTimeout(dismissTimeout);
                    if (showProgress) {
                        const progressBar = messageEl.querySelector('.progress-bar');
                        progressBar.style.transition = 'none';
                    }
                });
                
                messageEl.addEventListener('mouseleave', () => {
                    const remainingTime = duration * (parseFloat(messageEl.querySelector('.progress-bar')?.style.width || '0') / 100);
                    if (showProgress) {
                        const progressBar = messageEl.querySelector('.progress-bar');
                        progressBar.style.transition = `width ${remainingTime}ms linear`;
                        progressBar.style.width = '0%';
                    }
                    dismissTimeout = setTimeout(() => {
                        closeMessage(messageId);
                    }, remainingTime);
                });
            }
            
            return messageId;
        }
        
        // Close Message Function
        function closeMessage(id) {
            const messageEl = document.getElementById(id);
            if (!messageEl) return;
            
            messageEl.classList.add('hide');
            messageEl.classList.remove('show');
            
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.parentNode.removeChild(messageEl);
                }
            }, animationSpeed);
        }
        
        // Update Container Position
        function updateContainerPosition(position) {
            flashContainer.style.top = 'auto';
            flashContainer.style.right = 'auto';
            flashContainer.style.bottom = 'auto';
            flashContainer.style.left = 'auto';
            
            if (position.includes('top')) {
                flashContainer.style.top = '20px';
            } else {
                flashContainer.style.bottom = '20px';
            }
            
            if (position.includes('right')) {
                flashContainer.style.right = '20px';
            } else if (position.includes('left')) {
                flashContainer.style.left = '20px';
            } else {
                flashContainer.style.left = '50%';
                flashContainer.style.transform = 'translateX(-50%)';
            }
        }
        
        // Get Icon Based on Type
        function getIcon(type) {
            switch (type) {
                case 'success':
                    return `<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>`;
                case 'error':
                    return `<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>`;
                case 'warning':
                    return `<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>`;
                case 'info':
                default:
                    return `<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>`;
            }
        }
        
        // Get Colors Based on Type and Theme
        function getColors(type) {
            const themeColors = {
                indigo: {
                    success: { bg: '#f0fdf4', iconBg: '#22c55e', title: '#166534', text: '#166534', close: '#166534', progressBg: '#dcfce7', progress: '#22c55e' },
                    error: { bg: '#fef2f2', iconBg: '#ef4444', title: '#991b1b', text: '#991b1b', close: '#991b1b', progressBg: '#fee2e2', progress: '#ef4444' },
                    warning: { bg: '#fffbeb', iconBg: '#f59e0b', title: '#92400e', text: '#92400e', close: '#92400e', progressBg: '#fef3c7', progress: '#f59e0b' },
                    info: { bg: '#eff6ff', iconBg: '#3b82f6', title: '#1e40af', text: '#1e40af', close: '#1e40af', progressBg: '#dbeafe', progress: '#3b82f6' }
                },
            };
            
            // Apply style modifications
            let colors = { ...themeColors[currentTheme][type] };
            
            if (currentStyle === 'minimal') {
                colors.bg = '#ffffff';
                colors.progressBg = '#f3f4f6';
            } else if (currentStyle === 'bordered') {
                colors.bg = '#ffffff';
                // Add border color based on type
                colors.border = colors.progress;
            }
            
            return colors;
        }
        // Theme Buttons
        document.querySelectorAll('.theme-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                currentTheme = btn.dataset.theme;
                document.querySelectorAll('.theme-btn').forEach(b => {
                    b.style.outline = 'none';
                });
                btn.style.outline = '3px solid #000';
                btn.style.outlineOffset = '2px';
            });
        });
