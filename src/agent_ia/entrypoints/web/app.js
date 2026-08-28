/**
 * AGENT IA — Frontend Controller
 * Direct integration with FastAPI Gateway (:8000)
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const appContainer = document.getElementById('appContainer');
  const chatFeed = document.getElementById('chatFeed');
  const welcomeCard = document.getElementById('welcomeCard');
  const promptInput = document.getElementById('promptInput');
  const sendBtn = document.getElementById('sendBtn');
  const suggestionPills = document.getElementById('suggestionPills');
  const clearChatBtn = document.getElementById('clearChatBtn');
  const toggleSidebarBtn = document.getElementById('toggleSidebarBtn');
  const togglePanelBtn = document.getElementById('togglePanelBtn');
  const systemPulseDot = document.getElementById('systemPulseDot');
  const systemStatusText = document.getElementById('systemStatusText');
  const systemVersion = document.getElementById('systemVersion');
  const activeAgentSubtitle = document.getElementById('activeAgentSubtitle');

  let isGenerating = false;
  let messageHistory = [];

  // API Base URL (relative or port 8000)
  const API_BASE = window.location.origin.includes(':8000') 
    ? window.location.origin 
    : 'http://localhost:8000';

  // ─────────────────────────────────────────────────────────────
  // 1. Markdown Setup & Helpers
  // ─────────────────────────────────────────────────────────────
  function formatContent(text) {
    if (!text) return '';
    if (window.marked && typeof window.marked.parse === 'function') {
      return window.marked.parse(text);
    }
    // Fallback simple renderer
    return text
      .replace(/\n/g, '<br>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  function getAgentTagClass(agentName) {
    const name = (agentName || '').toLowerCase();
    if (name.includes('curador')) return 'curador';
    if (name.includes('estudio')) return 'estudio';
    if (name.includes('sync') || name.includes('notion')) return 'sync';
    if (name.includes('plan')) return 'plan';
    return 'hermes';
  }

  function getAgentAvatar(agentName) {
    const name = (agentName || '').toLowerCase();
    if (name.includes('curador')) return '🟠';
    if (name.includes('estudio')) return '🔵';
    if (name.includes('sync') || name.includes('notion')) return '🟢';
    if (name.includes('plan')) return '🟣';
    return '🧠';
  }

  function formatTime(date = new Date()) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  // ─────────────────────────────────────────────────────────────
  // 2. Chat Rendering
  // ─────────────────────────────────────────────────────────────
  function scrollToBottom() {
    chatFeed.scrollTo({
      top: chatFeed.scrollHeight,
      behavior: 'smooth'
    });
  }

  function renderUserMessage(text) {
    if (welcomeCard && welcomeCard.parentNode) {
      welcomeCard.style.display = 'none';
    }

    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `
      <div class="message-bubble">
        ${formatContent(text)}
      </div>
    `;
    chatFeed.appendChild(row);
    scrollToBottom();
  }

  function renderAssistantMessage(data) {
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    
    const agentName = data.agente || 'Hermes';
    const tagClass = getAgentTagClass(agentName);
    const avatar = getAgentAvatar(agentName);
    const formattedHtml = formatContent(data.mensaje || data.content || '');

    // Check if there is an interactive pending action or proposal
    let actionBoxHtml = '';
    if (data.accion_pendiente || (data.datos && data.datos.propuesta)) {
      actionBoxHtml = `
        <div class="action-box">
          <div class="action-prompt">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            Acción pendiente de confirmación:
          </div>
          <div class="action-buttons">
            <button class="btn-action btn-confirm" onclick="window.confirmAction('sí, adelante')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              Confirmar
            </button>
            <button class="btn-action btn-cancel" onclick="window.confirmAction('cancelar')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              Cancelar
            </button>
          </div>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="message-avatar">${avatar}</div>
      <div class="message-bubble">
        <div class="message-agent-header">
          <span class="agent-tag ${tagClass}">${agentName}</span>
          <span class="message-time">${formatTime()}</span>
        </div>
        <div class="message-text">
          ${formattedHtml}
        </div>
        ${actionBoxHtml}
      </div>
    `;

    chatFeed.appendChild(row);
    scrollToBottom();
  }

  function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message-row assistant typing-indicator-row';
    indicator.id = 'typingIndicator';
    indicator.innerHTML = `
      <div class="message-avatar">🧠</div>
      <div class="message-bubble typing-bubble">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    `;
    chatFeed.appendChild(indicator);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
  }

  // ─────────────────────────────────────────────────────────────
  // 3. API Communication
  // ─────────────────────────────────────────────────────────────
  async function sendMessage(text) {
    if (!text || !text.trim() || isGenerating) return;
    
    const message = text.trim();
    promptInput.value = '';
    adjustTextareaHeight();
    
    // Add user message to UI
    renderUserMessage(message);
    messageHistory.push({ role: 'user', content: message });

    // Show typing state
    isGenerating = true;
    sendBtn.disabled = true;
    showTypingIndicator();
    activeAgentSubtitle.textContent = 'Hermes está orquestando tu respuesta...';

    try {
      const response = await fetch(`${API_BASE}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mensaje: message })
      });

      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const data = await response.json();
      removeTypingIndicator();
      renderAssistantMessage(data);
      messageHistory.push({ role: 'assistant', ...data });
      activeAgentSubtitle.textContent = `Última respuesta de ${data.agente || 'Hermes'}`;

    } catch (err) {
      console.error('Error sending message:', err);
      removeTypingIndicator();
      renderAssistantMessage({
        agente: 'Sistema',
        mensaje: `⚠️ **Error de conexión con el API Gateway**: No se pudo enviar el mensaje a Hermes.\n\nVerifica que el servidor esté activo en \`${API_BASE}\`.`
      });
      activeAgentSubtitle.textContent = 'Error de comunicación con el Gateway';
    } finally {
      isGenerating = false;
      sendBtn.disabled = false;
      promptInput.focus();
    }
  }

  window.confirmAction = function(actionText) {
    sendMessage(actionText);
  };

  // ─────────────────────────────────────────────────────────────
  // 4. Health & System Status Polling
  // ─────────────────────────────────────────────────────────────
  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
      if (res.ok) {
        const data = await res.json();
        systemPulseDot.style.background = 'var(--status-online)';
        systemStatusText.textContent = 'Hermes Online';
        
        // Update agents in list
        if (data.agentes) {
          updateFleetUI(data.agentes);
        }
      } else {
        setOfflineStatus();
      }
    } catch {
      setOfflineStatus();
    }
  }

  function setOfflineStatus() {
    systemPulseDot.style.background = 'var(--status-offline)';
    systemStatusText.textContent = 'Gateway Desconectado';
  }

  function updateFleetUI(agentes) {
    const list = document.getElementById('agentFleetList');
    if (!list) return;
    // Highlight agents
    const items = list.querySelectorAll('.agent-item');
    items.forEach(item => {
      const agentKey = item.getAttribute('data-agent');
      if (agentes[agentKey] || agentKey === 'hermes') {
        const badge = item.querySelector('.agent-status-badge');
        if (badge) {
          badge.textContent = 'En Línea';
          badge.style.color = 'var(--status-online)';
        }
      }
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 5. Agent List Click Routing
  // ─────────────────────────────────────────────────────────────
  const fleetList = document.getElementById('agentFleetList');
  if (fleetList) {
    fleetList.addEventListener('click', (e) => {
      const item = e.target.closest('.agent-item');
      if (!item) return;

      // Update active styling
      fleetList.querySelectorAll('.agent-item').forEach(el => el.classList.remove('active'));
      item.classList.add('active');

      const agentKey = item.dataset.agent;
      const promptsMap = {
        'hermes': '⚡ ¿Cuál es el estado de todos los agentes?',
        'curador': '📥 Anota esto: ',
        'estudio': '📚 Iniciar repaso de flashcards',
        'sync': '🔄 Sincronizar mis notas de Notion con Obsidian',
        'plan': '🎯 Quiero un plan estratégico para: '
      };

      const starter = promptsMap[agentKey] || 'Hola';
      if (starter.endsWith(': ')) {
        promptInput.value = starter;
        promptInput.focus();
        adjustTextareaHeight();
      } else {
        sendMessage(starter);
      }
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 6. Right Panel Direct Actions (Sync & Quiz)
  // ─────────────────────────────────────────────────────────────
  const triggerSyncBtn = document.getElementById('triggerSyncBtn');
  if (triggerSyncBtn) {
    triggerSyncBtn.addEventListener('click', async () => {
      if (isGenerating) return;
      isGenerating = true;
      triggerSyncBtn.disabled = true;
      triggerSyncBtn.innerHTML = '<span>⏳</span> Sincronizando...';

      renderUserMessage('🔄 Ejecutando sincronización bidireccional (Notion ↔ Obsidian)...');
      showTypingIndicator('AgenteSync');

      try {
        const resp = await fetch(`${API_BASE}/sync/ejecutar`, { method: 'POST' });
        const data = await resp.json();
        removeTypingIndicator();
        renderAssistantMessage({
          mensaje: data.mensaje || 'Sincronización completada.',
          agente: 'AgenteSync',
          timestamp: new Date().toISOString()
        });
      } catch (err) {
        removeTypingIndicator();
        renderAssistantMessage({
          mensaje: `❌ Error al sincronizar: ${err.message}`,
          agente: 'AgenteSync',
          timestamp: new Date().toISOString()
        });
      } finally {
        isGenerating = false;
        triggerSyncBtn.disabled = false;
        triggerSyncBtn.innerHTML = '<span>🔄</span> Ejecutar Sincronización Ahora';
      }
    });
  }

  const triggerQuizBtn = document.getElementById('triggerQuizBtn');
  if (triggerQuizBtn) {
    triggerQuizBtn.addEventListener('click', () => {
      sendMessage('📚 Iniciar repaso de flashcards');
    });
  }

  // ─────────────────────────────────────────────────────────────
  // 7. Input Interactions & Shortcuts
  // ─────────────────────────────────────────────────────────────
  function adjustTextareaHeight() {
    promptInput.style.height = 'auto';
    promptInput.style.height = Math.min(promptInput.scrollHeight, 140) + 'px';
  }

  promptInput.addEventListener('input', adjustTextareaHeight);

  promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(promptInput.value);
    }
  });

  sendBtn.addEventListener('click', () => {
    sendMessage(promptInput.value);
  });

  // Suggestion Pills
  if (suggestionPills) {
    suggestionPills.addEventListener('click', (e) => {
      const btn = e.target.closest('.pill-btn');
      if (btn && btn.dataset.prompt) {
        const prompt = btn.dataset.prompt;
        if (prompt.endsWith(': ')) {
          promptInput.value = prompt;
          promptInput.focus();
          adjustTextareaHeight();
        } else {
          sendMessage(prompt);
        }
      }
    });
  }

  // Clear Chat Button
  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      chatFeed.innerHTML = '';
      if (welcomeCard) {
        welcomeCard.style.display = 'block';
        chatFeed.appendChild(welcomeCard);
      }
      messageHistory = [];
    });
  }

  // Toggle Sidebars
  if (toggleSidebarBtn) {
    toggleSidebarBtn.addEventListener('click', () => {
      appContainer.classList.toggle('sidebar-collapsed');
    });
  }

  if (togglePanelBtn) {
    togglePanelBtn.addEventListener('click', () => {
      appContainer.classList.toggle('panel-collapsed');
    });
  }

  // Global Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    // Ctrl+K to focus prompt
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      promptInput.focus();
    }
    // Ctrl+B to toggle left sidebar
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      appContainer.classList.toggle('sidebar-collapsed');
    }
  });

  // Initial load
  checkHealth();
  setInterval(checkHealth, 8000);
  promptInput.focus();
});
