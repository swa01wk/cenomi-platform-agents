from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class OrderRequest(BaseModel):
    order_id: str
    item: str

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return {"order_id": order_id, "item": "the item is rphone"}

@app.post("/orders")
def create_order(payload: OrderRequest):
    # Replace this with real logic
    return {"received": payload.order_id, "status": "the order has been created"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8001)