# Tool Registry API Documentation

## Overview

The Tool Registry provides three types of tools that can be registered via API endpoints. All endpoints are prefixed with `/v1`.

---

## Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique tool identifier |
| `type` | string | Yes | Tool type: `prebuilt`, `custom_function`, or `custom_api` |
| `name` | string | Yes | Tool name exposed to the LLM |
| `description` | string | Yes | Used by LLM for tool selection |
| `input_schema` | object | Yes | Object with `properties` field defining tool input parameters |
| `output_schema` | object | No | JSON Schema defining expected output (defaults to `{"type": "object"}`) |

---

## 1. Prebuilt Tool

**Endpoint:** `POST /v1/prebuilt`

**Use Case:** Register tools with built-in functionality.

**Payload:**
```json
{
  "id": "prebuilt_web_search",
  "type": "prebuilt",
  "name": "web_search",
  "description": "Search the web using a built-in provider",
  "input_schema": {
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query string"
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "results": {
        "type": "array"
      }
    }
  }
}
```

**Retrieve:** `GET /v1/prebuilt`

---

## 2. Custom Function Tool

**Endpoint:** `POST /v1/custom-function`

**Use Case:** Register tools that execute custom Python functions.

**Additional Fields:**
- `function` (optional): Name of the function to execute

**Payload:**
```json
{
  "id": "calculate_discount",
  "type": "custom_function",
  "name": "calculate_discount",
  "description": "Calculate discounted price for a product",
  "input_schema": {
    "properties": {
      "price": {
        "type": "number",
        "description": "Original price of the product"
      },
      "discount_percentage": {
        "type": "number",
        "description": "Discount percentage to apply"
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "final_price": {
        "type": "number"
      }
    }
  },
  "function": "calculate_discount_fn"
}
```

**Retrieve:** `GET /v1/custom-function`

---

## 3. Custom API Tool

**Endpoint:** `POST /v1/custom-api`

**Use Case:** Register tools that call external APIs.

**Additional Fields:**
- `api_url` (required): Target API endpoint
- `api_request_type` (required): HTTP method (`GET` or `POST`)
- `custom_message` (optional): Guides LLM to extract specific fields from API response

**Payload:**
```json
{
  "id": "get_user_orders",
  "type": "custom_api",
  "name": "get_user_orders",
  "description": "Fetch all orders for a user",
  "input_schema": {
    "properties": {
      "user_id": {
        "type": "string",
        "description": "Unique identifier of the user"
      }
    }
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "status_code": {
        "type": "number"
      },
      "response": {
        "type": "object"
      }
    }
  },
  "api_url": "https://api.example.com/orders",
  "api_request_type": "GET",
  "custom_message": "Extract only order_id, order_status, and total_price from the response."
}
```

**Retrieve:** `GET /v1/custom-api`

---

## Additional Endpoints

- **List all tools:** `GET /v1/`
- **Get tool by ID:** `GET /v1/{tool_id}`
- **Delete tool:** `DELETE /v1/{tool_id}`

---

## Notes

- `metadata.created_at` is automatically added to all tools upon creation
- Tool IDs must be unique across all types
- Input/output schemas follow JSON Schema specification
- All timestamps are in ISO 8601 format (UTC)
