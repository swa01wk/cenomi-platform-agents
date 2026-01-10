from fastapi import APIRouter, HTTPException
from src.registry.store import AgentRegistryStore
from .schemas import AgentCreate, AgentUpdate
import traceback

router = APIRouter(prefix="/v1/admin/agents", tags=["Admin: Agents"])
store = AgentRegistryStore()

@router.get("")
async def list_agents():
    return await store.alist_agents()

@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    a = await store.aget_agent(agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    return a

@router.post("")
async def create_agent(payload: AgentCreate):
    # basic stage sanity check: referenced fields exist
    field_keys = {f.key for f in payload.fields}
    for st in payload.stages:
        for rf in st.required_fields:
            if rf not in field_keys:
                raise HTTPException(status_code=400, detail=f"Stage '{st.stage_id}' references unknown field '{rf}'")
    try:
        return await store.acreate_agent(payload.model_dump())
    except ValueError as e:
        print(traceback.print_exc())
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{agent_id}")
async def patch_agent(agent_id: str, payload: AgentUpdate):
    try:
        return await store.aupdate_agent(agent_id, payload.model_dump(exclude_unset=True))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    try:
        await store.adelete_agent(agent_id)
        return {"message": "Deleted"}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
