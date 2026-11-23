#data_base/engine_sql.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import DB_URL, SQL_ECHO, MAX_WORKERS, MAX_OVERFLOWS
import asyncio
import logging


class Creation_engine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        self.ENGINE = create_async_engine(
            DB_URL,
            echo=SQL_ECHO,
            pool_size=MAX_WORKERS,
            max_overflow=MAX_OVERFLOWS,
            pool_pre_ping=True
        )
        
    def engine(self):
        return self.ENGINE

    async def close_engine(self):
        try:
            await self.ENGINE.dispose()
            
        except asyncio.CancelledError:
            self.logger.warning("El cierre del motor fue cancelado.")
            raise
                
        except Exception:
            self.logger.exception("Error al cerrar el motor de la base de datos.")
            raise
            

# Instancia única compartida por todo el proceso
creation_engine = Creation_engine()


async def close_engine():
    await creation_engine.close_engine()
        

#URL = "postgresql+asyncpg://usuario:password@localhost:5432/mi_base_datos"

#postgresql+asyncpg = Motor de base de datos y controlador de Python (asíncrono).

#usuario:password = Credenciales de acceso.

#localhost:5432 = Dirección del servidor y puerto de PostgreSQL.

#mi_base_datos = Nombre de la base de datos a la que accederás.
