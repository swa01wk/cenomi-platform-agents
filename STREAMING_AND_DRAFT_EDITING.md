# Streaming & Draft Editing Implementation Guide

## 1. Streaming AI Responses

### Overview
Added real-time streaming of AI responses using Server-Sent Events (SSE).

### New Endpoint
**POST `/v1/chat/stream`**

### Request Body
```json
{
  "session_id": "abc123",
  "message": "I want to submit a lead enquiry",
  "attachments": []
}
```

### Response Format (SSE)
The endpoint streams events in Server-Sent Events format:

```
data: {"type": "message", "content": "Hi! Let me help you..."}

data: {"type": "complete", "state": {...full_state...}}

data: [DONE]
```

### Event Types
1. **`message`** - Streamed chunks of the assistant's response
2. **`complete`** - Final state after processing (includes drafts, phase, etc.)
3. **`[DONE]`** - Indicates stream completion

### Frontend Integration Example (JavaScript)

```javascript
const eventSource = new EventSource('/v1/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: sessionId,
    message: userMessage
  })
});

let fullMessage = '';

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);

  if (data === '[DONE]') {
    eventSource.close();
    return;
  }

  if (data.type === 'message') {
    // Append to UI in real-time
    fullMessage += data.content;
    updateChatUI(fullMessage);
  }

  if (data.type === 'complete') {
    // Update state (drafts, phase, etc.)
    updateState(data.state);
  }
});

eventSource.addEventListener('error', (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
});
```

### Using fetch API (Alternative)

```javascript
const response = await fetch('/v1/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    session_id: sessionId,
    message: userMessage
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));

      if (data === '[DONE]') break;

      if (data.type === 'message') {
        appendToChat(data.content);
      }

      if (data.type === 'complete') {
        updateDrafts(data.state.drafts);
      }
    }
  }
}
```

---

## 2. Frontend Draft Editing

### Overview
Allows users to edit draft fields directly from the frontend UI. Changes are immediately reflected in the session state.

### New Endpoint
**POST `/v1/draft/update`**

### Request Body
```json
{
  "session_id": "abc123",
  "agent_id": "lead_enquiry_submission_agent",
  "field": "email",
  "value": "newemail@example.com"
}
```

### Response (Success)
```json
{
  "success": true,
  "drafts": {
    "lead_enquiry_submission_agent": {
      "first_name": "John",
      "email": "newemail@example.com",
      ...
    }
  },
  "phase": "collecting",
  "active_agent_id": "lead_enquiry_submission_agent"
}
```

### Response (Validation Failed)
```json
{
  "success": false,
  "error": "Invalid email format",
  "drafts": {
    "lead_enquiry_submission_agent": {
      "first_name": "John",
      ...
    }
  }
}
```

### Features
- **Real-time validation**: Runs the configured validator for the field (e.g., `email_validator`, `phone_validator`)
- **State persistence**: Updates are immediately saved to the session
- **Rollback on error**: If validation fails, the old value is retained

### Frontend Integration Example (React)

```jsx
const DraftEditor = ({ sessionId, agentId, drafts }) => {
  const [localDraft, setLocalDraft] = useState(drafts[agentId] || {});
  const [errors, setErrors] = useState({});

  const handleFieldChange = async (field, value) => {
    // Optimistic update
    setLocalDraft(prev => ({ ...prev, [field]: value }));

    try {
      const response = await fetch('/v1/draft/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          agent_id: agentId,
          field: field,
          value: value
        })
      });

      const data = await response.json();

      if (!data.success) {
        // Validation failed - show error and revert
        setErrors(prev => ({ ...prev, [field]: data.error }));
        setLocalDraft(data.drafts[agentId]);
      } else {
        // Success - clear error
        setErrors(prev => ({ ...prev, [field]: null }));
        setLocalDraft(data.drafts[agentId]);
      }
    } catch (error) {
      console.error('Failed to update draft:', error);
    }
  };

  return (
    <div className="draft-editor">
      <h3>Review Your Information</h3>
      {Object.entries(localDraft).map(([key, value]) => (
        <div key={key} className="field">
          <label>{key}</label>
          <input
            type="text"
            value={value}
            onChange={(e) => handleFieldChange(key, e.target.value)}
          />
          {errors[key] && <span className="error">{errors[key]}</span>}
        </div>
      ))}
    </div>
  );
};
```

### Complete UI Flow Example

```jsx
const ChatInterface = () => {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [phase, setPhase] = useState('supervisor');
  const [agentId, setAgentId] = useState(null);

  // Initialize session
  useEffect(() => {
    fetch('/v1/session', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setSessionId(data.session_id);
        setMessages([{ role: 'assistant', content: data.assistant_message }]);
      });
  }, []);

  // Send message with streaming
  const sendMessage = async (message) => {
    const response = await fetch('/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let assistantMessage = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));

          if (data.type === 'message') {
            assistantMessage += data.content;
            // Update UI in real-time
            setMessages(prev => [...prev.slice(0, -1), {
              role: 'assistant',
              content: assistantMessage
            }]);
          }

          if (data.type === 'complete') {
            setDrafts(data.state.drafts);
            setPhase(data.state.phase);
            setAgentId(data.state.active_agent_id);
          }
        }
      }
    }
  };

  return (
    <div className="chat-interface">
      <ChatMessages messages={messages} />

      {/* Show draft editor in confirm phase */}
      {phase === 'confirm' && agentId && (
        <DraftEditor
          sessionId={sessionId}
          agentId={agentId}
          drafts={drafts}
          onUpdate={(updatedDrafts) => setDrafts(updatedDrafts)}
        />
      )}

      <ChatInput onSend={sendMessage} />
    </div>
  );
};
```

---

## Benefits

### Streaming
- **Better UX**: Users see responses immediately instead of waiting
- **Lower perceived latency**: Response feels faster even if total time is the same
- **Progressive rendering**: Can start reading while AI is still generating

### Draft Editing
- **User control**: Let users fix typos or update info without retyping
- **Faster corrections**: Direct edit instead of "change email to X"
- **Visual feedback**: Users see their data in a form-like interface
- **Validation**: Immediate feedback on invalid inputs

---

## Technical Notes

### Streaming Implementation Details
- Uses LangGraph's `.astream()` method
- Streams over Server-Sent Events (SSE)
- Each node update in the graph can emit events
- Final state is sent after streaming completes

### Draft Update Implementation Details
- Directly modifies the session state in memory
- Runs configured validators (email, phone, etc.)
- Validates before storing (prevents invalid data)
- Returns updated state so frontend can sync

### Session State Persistence
Both endpoints modify the `SESSIONS` dict, which stores state in memory. For production:
- Consider using Redis or a database for persistence
- Add session expiration logic
- Handle concurrent updates with locks

---

## Testing

### Test Streaming Endpoint
```bash
curl -N -X POST http://localhost:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test123", "message": "I want to submit a lead enquiry"}'
```

### Test Draft Update Endpoint
```bash
curl -X POST http://localhost:8000/v1/draft/update \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test123",
    "agent_id": "lead_enquiry_submission_agent",
    "field": "email",
    "value": "newemail@example.com"
  }'
```
