import requests

BASE_URL = "http://127.0.0.1:8000/v1"

def log(step, response):
    print(f"{step}: {response.status_code}")


# ---------- PAYLOADS (hidden from output) ----------

PREBUILT_TOOL = {
    "id": "prebuilt_web_search",
    "type": "prebuilt",
    "name": "web_search",
    "description": "Search the web",
    "input_schema": {"type": "object"}
}

CUSTOM_FUNCTION_TOOL = {
    "id": "calculate_discount",
    "type": "custom_function",
    "name": "calculate_discount",
    "description": "Calculate discount",
    "input_schema": {"type": "object"},
    "function": "calculate_discount_fn"
}

CUSTOM_API_TOOL = {
    "id": "get_user_orders",
    "type": "custom_api",
    "name": "get_user_orders",
    "description": "Fetch orders",
    "input_schema": {"type": "object"},
    "api_url": "https://api.example.com/orders",
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


# # ---------- MODIFY ----------

# log(
#     "Modify Prebuilt Tool",
#     requests.put(
#         f"{BASE_URL}/{prebuilt_id}",
#         json={"description": "Updated web search tool"}
#     )
# )

# log(
#     "Modify Custom Function Tool",
#     requests.put(
#         f"{BASE_URL}/{function_id}",
#         json={
#             "description": "Updated discount calculator",
#             "function": "updated_discount_fn"
#         }
#     )
# )

# log(
#     "Modify Custom API Tool",
#     requests.put(
#         f"{BASE_URL}/{api_id}",
#         json={
#             "description": "Updated order fetcher",
#             "custom_message": "Extract order_id and total_price"
#         }
#     )
# )


# # ---------- LIST ----------

# log("List Prebuilt Tools", requests.get(f"{BASE_URL}/prebuilt"))
# log("List Custom Function Tools", requests.get(f"{BASE_URL}/custom-function"))
# log("List Custom API Tools", requests.get(f"{BASE_URL}/custom-api"))
# log("List All Tools", requests.get(f"{BASE_URL}/"))


# # ---------- GET BY ID ----------

# log("Get Prebuilt Tool", requests.get(f"{BASE_URL}/{prebuilt_id}"))
# log("Get Function Tool", requests.get(f"{BASE_URL}/{function_id}"))
# log("Get API Tool", requests.get(f"{BASE_URL}/{api_id}"))


# # ---------- DELETE ----------

# log("Delete Prebuilt Tool", requests.delete(f"{BASE_URL}/{prebuilt_id}"))
# log("Delete Function Tool", requests.delete(f"{BASE_URL}/{function_id}"))
# log("Delete API Tool", requests.delete(f"{BASE_URL}/{api_id}"))


# # ---------- VERIFY ----------

# log("Verify Prebuilt Deleted", requests.get(f"{BASE_URL}/{prebuilt_id}"))

# print("\n✅ ALL TESTS (INCLUDING MODIFY) PASSED")
