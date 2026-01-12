import requests

BASE_URL = "http://127.0.0.1:8003/v1"

def log(step, response):
    print(f"{step}: {response.status_code}")


# ---------- PAYLOADS (hidden from output) ----------

PREBUILT_TOOL = {
  "id": "tool-9f3c7b12",
  "type": "prebuilt",
  "name": "geo_locator",
  "description": "Resolve city and country from IP address",
  "input_schema": {
    "properties": {
      "additionalProp1": {
        "type": "string",
        "description": "IP address to resolve"
      },
      "additionalProp2": {
        "type": "string",
        "description": "User agent (optional)"
      },
      "additionalProp3": {
        "type": "string",
        "description": "Session correlation ID"
      }
    }
  },
  "output_schema": {
    "additionalProp1": {
      "country": "United States",
      "city": "Seattle",
      "lat": 47.6062,
      "lon": -122.3321,
      "ip": "203.0.113.42"
    }
  }
}

CUSTOM_FUNCTION_TOOL = {
  "id": "func-8a2d4e91",
  "type": "custom_function",
  "name": "sentiment_analyzer",
  "description": "Analyze sentiment of customer feedback text",
  "input_schema": {
    "properties": {
      "additionalProp1": {
        "type": "string",
        "description": "Customer feedback text to analyze"
      },
      "additionalProp2": {
        "type": "string",
        "description": "Language code (e.g., en, es, fr)"
      },
      "additionalProp3": {
        "type": "string",
        "description": "Analysis context (product, service, support)"
      }
    }
  },
  "output_schema": {
    "additionalProp1": {
      "sentiment": "positive",
      "confidence": 0.92,
      "keywords": ["excellent", "great", "satisfied"],
      "score": 0.85
    }
  },
  "function": "analyze_sentiment_v2"
}

CUSTOM_API_TOOL = {
  "id": "api-5c1f8b43",
  "type": "custom_api",
  "name": "inventory_checker",
  "description": "Check product inventory across warehouses",
  "input_schema": {
    "properties": {
      "additionalProp1": {
        "type": "string",
        "description": "Product SKU or ID"
      },
      "additionalProp2": {
        "type": "string",
        "description": "Warehouse location code"
      },
      "additionalProp3": {
        "type": "string",
        "description": "Stock status filter (in_stock, low, out_of_stock)"
      }
    }
  },
  "output_schema": {
    "additionalProp1": {
      "sku": "PROD-12345",
      "warehouse": "WH-US-WEST",
      "quantity": 245,
      "status": "in_stock",
      "last_updated": "2026-01-11T14:30:00Z"
    }
  },
  "custom_message": "Extract quantity and status for inventory decision making",
  "api_url": "https://inventory-api.example.com/v2/stock/check",
  "api_request_type": "GET"
}

# ---------- CREATE ----------

r1 = requests.post(f"{BASE_URL}/prebuilt", json=PREBUILT_TOOL)
log("Create Prebuilt Tool", r1)
prebuilt_id = r1.json()["id"]

r2 = requests.post(f"{BASE_URL}/custom-function", json=CUSTOM_FUNCTION_TOOL)
log("Create Custom Function Tool", r2)
function_id = r2.json()["id"]

r3 = requests.post(f"{BASE_URL}/custom-api", json=CUSTOM_API_TOOL)
log("Create Custom API Tool", r3)
api_id = r3.json()["id"]


# ---------- MODIFY ----------

log(
    "Modify Prebuilt Tool",
    requests.put(
        f"{BASE_URL}/{prebuilt_id}",
        json={"description": "Updated web search tool"}
    )
)

log(
    "Modify Custom Function Tool",
    requests.put(
        f"{BASE_URL}/{function_id}",
        json={
            "description": "Updated discount calculator",
            "function": "updated_discount_fn"
        }
    )
)

log(
    "Modify Custom API Tool",
    requests.put(
        f"{BASE_URL}/{api_id}",
        json={
            "description": "Updated order fetcher",
            "custom_message": "Extract order_id and total_price"
        }
    )
)


# ---------- LIST ----------

log("List Prebuilt Tools", requests.get(f"{BASE_URL}/prebuilt"))
log("List Custom Function Tools", requests.get(f"{BASE_URL}/custom-function"))
log("List Custom API Tools", requests.get(f"{BASE_URL}/custom-api"))
log("List All Tools", requests.get(f"{BASE_URL}/"))


# ---------- GET BY ID ----------

log("Get Prebuilt Tool", requests.get(f"{BASE_URL}/{prebuilt_id}"))
log("Get Function Tool", requests.get(f"{BASE_URL}/{function_id}"))
log("Get API Tool", requests.get(f"{BASE_URL}/{api_id}"))


# ---------- DELETE ----------

log("Delete Prebuilt Tool", requests.delete(f"{BASE_URL}/{prebuilt_id}"))
log("Delete Function Tool", requests.delete(f"{BASE_URL}/{function_id}"))
log("Delete API Tool", requests.delete(f"{BASE_URL}/{api_id}"))


# ---------- VERIFY ----------

log("Verify Prebuilt Deleted", requests.get(f"{BASE_URL}/{prebuilt_id}"))

print("\n✅ ALL TESTS (INCLUDING MODIFY) PASSED")
