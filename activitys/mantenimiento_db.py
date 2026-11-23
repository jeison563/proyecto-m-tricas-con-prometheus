#activitys/mantenimiento_db.py
from temporalio import activity

from data_base.mantenimiento import mantenimiento


@activity.defn
async def mantenimiento_db() -> dict:
    return await mantenimiento()
