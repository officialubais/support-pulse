// SupportPulse Web App Logic

let currentSessionId = null;

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('chat-form');
  const clearBtn = document.getElementById('clear-chat-btn');

  form.addEventListener('submit', handleFormSubmit);
  clearBtn.addEventListener('click', clearChat);
});

function insertPrompt(text) {
  const input = document.getElementById('user-input');
  input.value = text;
  input.focus();
}

function sendQuickMessage(text) {
  insertPrompt(text);
  handleFormSubmit(new Event('submit'));
}

async function handleFormSubmit(e) {
  e.preventDefault();
  const input = document.getElementById('user-input');
  const text = input.value.trim();

  if (!text) return;

  // Add user message to chat UI
  appendMessage('user', text);
  input.value = '';

  // Show typing indicator
  const typingElem = appendTypingIndicator();

  try {
    const responseText = await queryAgent(text);
    typingElem.remove();
    appendMessage('assistant', responseText);
  } catch (err) {
    typingElem.remove();
    appendMessage('assistant', `⚠️ **Error communicating with agent:** ${err.message}`);
  }
}

async function queryAgent(userText) {
  // Use A2A JSON-RPC Endpoint
  const endpoint = '/a2a/app';
  const payload = {
    jsonrpc: "2.0",
    id: Date.now(),
    method: "message/send",
    params: {
      message: {
        messageId: "msg-" + Date.now(),
        role: "user",
        parts: [{ kind: "text", text: userText }]
      }
    }
  };

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    throw new Error(`HTTP error ${res.status}`);
  }

  const data = await res.json();
  if (data.error) {
    throw new Error(data.error.message || "RPC Error");
  }

  // Extract agent text response
  const history = data.result?.history || [];
  for (let i = history.length - 1; i >= 0; i--) {
    const item = history[i];
    if (item.role === 'agent' && item.parts) {
      for (const part of item.parts) {
        if (part.kind === 'text') {
          return part.text;
        }
      }
    }
  }

  return "I'm sorry, I couldn't process your request.";
}

function appendMessage(role, content) {
  const chat = document.getElementById('chat-messages');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'assistant' ? '⚡' : '👤';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';

  // Format basic markdown bolding & newlines
  const formattedContent = content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');

  contentDiv.innerHTML = formattedContent;

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(contentDiv);
  chat.appendChild(msgDiv);

  chat.scrollTop = chat.scrollHeight;
  return msgDiv;
}

function appendTypingIndicator() {
  const chat = document.getElementById('chat-messages');
  const msgDiv = document.createElement('div');
  msgDiv.className = 'message assistant typing';

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = '⚡';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  contentDiv.innerHTML = `
    <div class="typing-dots">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(contentDiv);
  chat.appendChild(msgDiv);
  chat.scrollTop = chat.scrollHeight;
  return msgDiv;
}

function clearChat() {
  const chat = document.getElementById('chat-messages');
  chat.innerHTML = `
    <div class="message assistant">
      <div class="avatar">⚡</div>
      <div class="message-content">
        <p>Chat cleared! How can I assist you with your customer support needs?</p>
      </div>
    </div>
  `;
}
