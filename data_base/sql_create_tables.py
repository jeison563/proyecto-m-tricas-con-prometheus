# data_base/sql_create_tables.py
import logging
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
    insert,
    text,
)
from sqlalchemy.exc import CompileError, IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from data_base.engine_sql import creation_engine

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20), default="user", server_default="user")
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Host(Base):
    __tablename__ = "hosts"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_hosts_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Table_data_metrics(Base):
    """Tabla PARTICIONADA por día (created_at). La crea la migración con SQL manual."""

    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_host_created", "host_id", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    host_id: Mapped[int] = mapped_column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"))
    cpu_percent: Mapped[int] = mapped_column(Integer, default=0)
    memory_percent: Mapped[int] = mapped_column(Integer, default=0)
    memory_available: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_percent: Mapped[int] = mapped_column(Integer, default=0)
    disk_used: Mapped[int] = mapped_column(BigInteger, default=0)


class Metrics1m(Base):
    """Resumen por minuto (promedio y máximo) para conservar historia a largo plazo."""

    __tablename__ = "metrics_1m"

    host_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True
    )
    minuto: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    muestras: Mapped[int] = mapped_column(Integer)
    cpu_avg: Mapped[float] = mapped_column(Float)
    cpu_max: Mapped[int] = mapped_column(Integer)
    memory_avg: Mapped[float] = mapped_column(Float)
    memory_max: Mapped[int] = mapped_column(Integer)
    disk_avg: Mapped[float] = mapped_column(Float)
    disk_max: Mapped[int] = mapped_column(Integer)
    memory_available_min: Mapped[int] = mapped_column(BigInteger)
    disk_used_max: Mapped[int] = mapped_column(BigInteger)


class Table_data_analisis(Base):
    __tablename__ = "metrics_analisis"
    __table_args__ = (Index("ix_analisis_host_created", "host_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    host_id: Mapped[int] = mapped_column(Integer, ForeignKey("hosts.id", ondelete="CASCADE"))
    metricas: Mapped[dict] = mapped_column(JSON)
    analisis: Mapped[dict] = mapped_column(JSON)


class Engine_tables:
    def __init__(self):
        self.Engine = creation_engine.engine()
        self._session_factory = async_sessionmaker(self.Engine, expire_on_commit=False)

    def get_session(self) -> AsyncSession:
        """Obtiene una sesión asíncrona."""
        return self._session_factory()

    async def _insertar(self, modelo, data: dict, nombre: str):
        # Insert "Core" (no ORM): en una tabla particionada con PK (id, created_at)
        # evita que el ORM tenga que recuperar los valores generados por la base.
        try:
            async with self.get_session() as session:
                async with session.begin():
                    await session.execute(insert(modelo).values(**data))
        except (CompileError, IntegrityError) as e:
            # claves que no son columnas, o host_id inexistente: no sirve reintentar
            raise ValueError(f"Datos inválidos para {nombre}: {e.__class__.__name__}") from e
        except SQLAlchemyError as e:
            raise RuntimeError(f"Error al insertar en {nombre}") from e

    async def insert_metrics_data(self, data: dict):
        await self._insertar(Table_data_metrics, data, "metrics")

    async def insert_metrics_analisis(self, data: dict):
        await self._insertar(Table_data_analisis, data, "metrics_analisis")


_tablas = Engine_tables()
insert_metrics_data = _tablas.insert_metrics_data
insert_metrics_analisis = _tablas.insert_metrics_analisis


async def get_db():
    """Dependencia de FastAPI: una sesión por petición."""
    async with _tablas.get_session() as session:
        yield session
