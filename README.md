# Agent Platform PoC (LangGraph Pattern A)

This repo provides:
- Admin APIs to create/configure agents (subagents)
- Tenant chat API that runs supervisor + generic subagent runner (Pattern A)
- Supports multi-stage agents (e.g., Lead Enquiry)

## Setup
cp .env.example .env   # set OPENAI_API_KEY
pip install -r requirements.txt

## Run
uvicorn src.main:app --reload --port 8081

## Admin: Create Agents
POST /v1/admin/agents   (see payload examples below)

## Tenant Chat
POST /v1/session
POST /v1/chat  {session_id, message, attachments?}

### Typical flow
1) Create session -> assistant asks service type list
2) Tenant selects Lead Enquiry
3) Bot collects fields, runs tools, then asks for documents
4) Upload documents using attachments in chat
5) Bot shows final form -> tenant says "yes" -> submits

## Examples
Create session:
curl -X POST http://localhost:8081/v1/session

Chat:
curl -X POST http://localhost:8081/v1/chat \
 -H "Content-Type: application/json" \
 -d '{"session_id":"SID","message":"Lead Enquiry"}'

Upload docs:
curl -X POST http://localhost:8081/v1/chat \
 -H "Content-Type: application/json" \
 -d '{"session_id":"SID","message":"Uploading docs","attachments":["cr.pdf","brand_profile.pdf"]}'
