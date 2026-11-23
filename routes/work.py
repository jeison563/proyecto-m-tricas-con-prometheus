# routes/work.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError

from core.config import TASK_QUEUE
from core.seguridad import require_admin
from fastapi import Request
from temporal.workflows import MiWorkflow

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runs", status_code=202, dependencies=[Depends(require_admin)])
async def create_run(request: Request):
    client = request.app.state.temporal
    try:
        handle = await client.start_workflow(
            MiWorkflow.run,
            id="rates-monitor",
            task_queue=TASK_QUEUE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except RPCError as e:
        logger.exception("Error de comunicación con Temporal")
        raise HTTPException(status_code=502, detail="No se pudo contactar con Temporal") from e
    except (TypeError, ValueError) as e:
        logger.exception("Parámetros inválidos al iniciar el workflow")
        raise HTTPException(status_code=500, detail="Parámetros inválidos del workflow") from e

    return {"workflow_id": handle.id, "run_id": handle.result_run_id}
