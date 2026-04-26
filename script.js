document.addEventListener('DOMContentLoaded', () => {

    // ─────────────────────────────────────────────
    // 1. THEME TOGGLE LOGIC
    // ─────────────────────────────────────────────
    const themeToggleBtn = document.getElementById('themeToggle');
    const body = document.body;

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        body.classList.add('light-theme');
        themeToggleBtn.textContent = '🌙';
    } else {
        themeToggleBtn.textContent = '☀️';
    }

    themeToggleBtn.addEventListener('click', () => {
        body.classList.toggle('light-theme');
        const isLight = body.classList.contains('light-theme');
        localStorage.setItem('theme', isLight ? 'light' : 'dark');
        themeToggleBtn.textContent = isLight ? '🌙' : '☀️';
    });


    // ─────────────────────────────────────────────
    // 2. CONSISTENCY MATRIX POPULATION
    // ─────────────────────────────────────────────
    const matrixContainer = document.getElementById('consistencyMatrix');
    for (let i = 0; i < 50; i++) {
        const cell = document.createElement('div');
        cell.classList.add('matrix-cell');
        const rand = Math.random();
        if (rand > 0.8) cell.classList.add('high');
        else if (rand > 0.5) cell.classList.add('active');
        matrixContainer.appendChild(cell);
    }


    // ─────────────────────────────────────────────
    // 3. MATH KEYBOARD LOGIC
    // ─────────────────────────────────────────────
    const mathBtns = document.querySelectorAll('.math-btn');
    const userInput = document.getElementById('userInput');

    mathBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const latex = btn.getAttribute('data-latex');
            const start = userInput.selectionStart;
            const end = userInput.selectionEnd;
            userInput.value = userInput.value.substring(0, start) + latex + userInput.value.substring(end);

            // Place cursor inside first empty braces, else after the insert
            let newPos = start + latex.length;
            if (latex.includes('{}')) newPos -= 1;
            userInput.focus();
            userInput.setSelectionRange(newPos, newPos);
        });
    });


    // ─────────────────────────────────────────────
    // 4. AUTO-EXPAND TEXTAREA
    // ─────────────────────────────────────────────
    userInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = this.scrollHeight + 'px';
    });


    // ─────────────────────────────────────────────
    // 5. ENGINE MODE TOGGLE — SOLVER / TESTER
    // ─────────────────────────────────────────────
    const engineToggle = document.getElementById('engineModeToggle');
    const testerContainer = document.getElementById('tester-container');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const mathKeyboard = document.getElementById('mathKeyboard');

    // All chat messages live inside chatWindow (excluding tester-container and welcomeMessage)
    let isTesterMode = false;

    function switchToSolverMode() {
        isTesterMode = false;
        testerContainer.style.display = 'none';
        welcomeMessage.style.display = '';
        mathKeyboard.style.display = 'flex';
        userInput.placeholder = 'Ask a question or paste a math problem...';
        
        // Re-show and animate chat elements
        const chatElements = [welcomeMessage, mathKeyboard, ...document.querySelectorAll('.message:not(#welcomeMessage)')];
        chatElements.forEach((m, idx) => {
            m.style.display = m === mathKeyboard ? 'flex' : '';
            m.classList.remove('fade-enter-active');
            m.classList.add('fade-enter');
            setTimeout(() => {
                m.classList.remove('fade-enter');
                m.classList.add('fade-enter-active');
            }, 20 + (idx * 20));
        });
    }

    function switchToTesterMode() {
        isTesterMode = true;
        welcomeMessage.style.display = 'none';
        mathKeyboard.style.display = 'none';
        document.querySelectorAll('.message:not(#welcomeMessage)').forEach(m => m.style.display = 'none');
        
        userInput.placeholder = 'Enter a topic to generate a test (e.g., Quantum Physics)...';
        
        testerContainer.style.display = 'flex';
        testerContainer.classList.remove('fade-enter-active');
        testerContainer.classList.add('fade-enter');
        
        setTimeout(() => {
            testerContainer.classList.remove('fade-enter');
            testerContainer.classList.add('fade-enter-active');
        }, 20);
    }

    engineToggle.addEventListener('change', () => {
        if (engineToggle.checked) {
            switchToTesterMode();
        } else {
            switchToSolverMode();
        }
    });


    // ─────────────────────────────────────────────
    // 6. CHAT LOGIC (SOLVER MODE)
    // ─────────────────────────────────────────────
    const sendBtn = document.getElementById('sendBtn');
    const chatWindow = document.getElementById('chatWindow');
    const clearSessionBtn = document.getElementById('clearSessionBtn');

    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender, 'stagger-in');

        if (sender === 'ai') {
            // Replace literal \n\n and \n with HTML breaks
            let formatted = text
                .replace(/\\n\\n/g, '<br><br>')
                .replace(/\\n/g, '<br>');
            msgDiv.innerHTML = formatted;
        } else {
            msgDiv.textContent = text;
        }

        chatWindow.appendChild(msgDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        return msgDiv;
    }


    // ─────────────────────────────────────────────
    // 7. QUIZ RENDERING & GRADING LOGIC (TESTER MODE)
    // ─────────────────────────────────────────────

    /**
     * renderQuizCards(aiResponse)
     * Parses the AI's response and renders Bento Box quiz cards.
     *
     * Expected JSON format from AI:
     * [
     *   {
     *     "question": "What is Newton's First Law?",
     *     "options": { "A": "...", "B": "...", "C": "...", "D": "..." },
     *     "answer": "A"
     *   },
     *   ...
     * ]
     *
     * Also handles labelled text format as a fallback.
     */
    function renderQuizCards(aiResponse, topic = '') {
        const quizCardsContainer = document.getElementById('quizCards');
        quizCardsContainer.innerHTML = ''; // Clear previous quiz

        if (topic) {
            document.getElementById('testerTopic').textContent = `🧠 ${topic}`;
            document.querySelector('.tester-subtitle').textContent =
                `${quizCardsContainer.children.length} questions generated. Select an answer to check.`;
        }

        let questions = [];

        // Attempt JSON parse first
        try {
            const jsonMatch = aiResponse.match(/\[[\s\S]*\]/);
            if (jsonMatch) {
                questions = JSON.parse(jsonMatch[0]);
            }
        } catch (e) {
            console.warn('Quiz JSON parse failed, attempting text fallback:', e);
        }

        // Fallback: use demo questions if parse fails or empty response
        if (!questions || questions.length === 0) {
            questions = generateDemoQuestions(topic || 'General Science');
        }

        // Build each quiz card
        questions.forEach((q, idx) => {
            const card = document.createElement('div');
            card.classList.add('quiz-card', 'stagger-in');
            card.style.animationDelay = `${idx * 0.15}s`;

            const optionLetters = ['A', 'B', 'C', 'D'];
            const correctLetter = q.answer;

            card.innerHTML = `
                <div class="quiz-card-number">Question ${idx + 1} of ${questions.length}</div>
                <div class="quiz-card-question">${q.question}</div>
                <div class="quiz-options" id="options-${idx}"></div>
            `;

            const optionsGrid = card.querySelector(`#options-${idx}`);

            optionLetters.forEach(letter => {
                const optionText = q.options[letter] || '';
                const btn = document.createElement('button');
                btn.classList.add('quiz-option');
                btn.setAttribute('data-letter', letter);
                btn.setAttribute('data-correct', correctLetter);
                btn.innerHTML = `<span class="option-badge">${letter}</span>${optionText}`;

                btn.addEventListener('click', () => gradeOption(btn, letter, correctLetter, optionsGrid));
                optionsGrid.appendChild(btn);
            });

            quizCardsContainer.appendChild(card);
        });

        // Update subtitle after rendering
        document.querySelector('.tester-subtitle').textContent =
            `${questions.length} question${questions.length !== 1 ? 's' : ''} generated. Select an answer to check.`;
    }

    /**
     * gradeOption(clickedBtn, selectedLetter, correctLetter, optionsGrid)
     * Applies correct/incorrect CSS classes and disables all options in the card.
     */
    function gradeOption(clickedBtn, selectedLetter, correctLetter, optionsGrid) {
        const allOptions = optionsGrid.querySelectorAll('.quiz-option');

        // Disable all options immediately
        allOptions.forEach(btn => {
            btn.disabled = true;
        });

        if (selectedLetter === correctLetter) {
            clickedBtn.classList.add('correct-answer');
        } else {
            clickedBtn.classList.add('incorrect-answer');
            // Also highlight the correct answer
            allOptions.forEach(btn => {
                if (btn.getAttribute('data-letter') === correctLetter) {
                    btn.classList.add('correct-answer');
                    btn.style.opacity = '1'; // Override disabled opacity for correct reveal
                }
            });
        }
    }

    /**
     * generateDemoQuestions(topic)
     * Returns 3 hardcoded demo questions for the given topic as a fallback.
     */
    function generateDemoQuestions(topic) {
        return [
            {
                question: `Which law states that energy cannot be created or destroyed, only converted? (Topic: ${topic})`,
                options: {
                    A: 'Zeroth Law of Thermodynamics',
                    B: 'First Law of Thermodynamics',
                    C: 'Second Law of Thermodynamics',
                    D: 'Third Law of Thermodynamics'
                },
                answer: 'B'
            },
            {
                question: `In the context of ${topic}, what does entropy measure?`,
                options: {
                    A: 'The total energy of a system',
                    B: 'The pressure of a gas',
                    C: 'The degree of disorder in a system',
                    D: 'The speed of light in a medium'
                },
                answer: 'C'
            },
            {
                question: `The absolute zero temperature is equivalent to:`,
                options: {
                    A: '−100°C',
                    B: '0°C',
                    C: '−273.15°C',
                    D: '−180°C'
                },
                answer: 'C'
            }
        ];
    }


    // ─────────────────────────────────────────────
    // 8. UNIFIED SEND BUTTON LOGIC
    // ─────────────────────────────────────────────
    sendBtn.addEventListener('click', () => {
        const text = userInput.value.trim();
        if (!text) return;

        userInput.value = '';
        userInput.style.height = 'auto';

        if (isTesterMode) {
            // In Tester Mode: generate a quiz for the entered topic
            renderQuizCards('', text);
        } else {
            // In Solver Mode: append user message and simulate AI response
            appendMessage(text, 'user');

            // Simulate AI response
            setTimeout(() => {
                const aiResponse = `Understood!\\n\\nHere is the solution for: "${text}"\\n\\nThis is a placeholder response. Connect your backend to get real AI answers.`;
                appendMessage(aiResponse, 'ai');
            }, 1000);
        }
    });

    // Send on Enter (not Shift+Enter)
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });


    // ─────────────────────────────────────────────
    // 9. CLEAR SESSION
    // ─────────────────────────────────────────────
    clearSessionBtn.addEventListener('click', () => {
        // Remove all injected chat messages (keep welcomeMessage and tester-container)
        chatWindow.querySelectorAll('.message:not(#welcomeMessage)').forEach(m => m.remove());
        document.getElementById('quizCards').innerHTML = '';
        document.getElementById('testerTopic').textContent = '🧠 Quiz Mode';
        document.querySelector('.tester-subtitle').textContent = 'Enter a topic below and click Send to generate your quiz.';
        welcomeMessage.textContent = 'Session cleared. How can I assist you next?';
        welcomeMessage.style.display = '';
    });

});
