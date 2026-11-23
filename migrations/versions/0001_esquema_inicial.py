#migrations/versions/0001_esquema_inicial.py
"""esquema inicial: users, hosts, metrics particionada, promedios por minuto, análisis

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

PREFIJO = "metrics_p"
DIAS_ADELANTE = 7


def upgrade() -> None:
    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False, server_default="user"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ---------- hosts ----------
    op.create_table(
        "hosts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "name", name="uq_hosts_owner_name"),
    )
    op.create_index("ix_hosts_owner_id", "hosts", ["owner_id"])

    # ---------- metrics: tabla padre PARTICIONADA por rango de fecha ----------
    op.execute(
        """
        CREATE TABLE metrics (
            id               BIGSERIAL,
            created_at       timestamptz NOT NULL DEFAULT now(),
            host_id          integer     NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
            cpu_percent      integer     NOT NULL DEFAULT 0,
            memory_percent   integer     NOT NULL DEFAULT 0,
            memory_available bigint      NOT NULL DEFAULT 0,
            disk_percent     integer     NOT NULL DEFAULT 0,
            disk_used        bigint      NOT NULL DEFAULT 0,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at)
        """
    )
    # Un índice sobre la tabla padre se crea automáticamente en cada partición
    op.execute("CREATE INDEX ix_metrics_host_created ON metrics (host_id, created_at DESC)")

    # Particiones iniciales: hoy y los próximos días (UTC)
    hoy = datetime.now(timezone.utc).date()
    for i in range(DIAS_ADELANTE + 1):
        dia = hoy + timedelta(days=i)
        sig = dia + timedelta(days=1)
        op.execute(
            f"CREATE TABLE IF NOT EXISTS {PREFIJO}{dia:%Y%m%d} PARTITION OF metrics "
            f"FOR VALUES FROM ('{dia} 00:00:00+00') TO ('{sig} 00:00:00+00')"
        )

    # ---------- metrics_1m: resumen por minuto ----------
    op.create_table(
        "metrics_1m",
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("minuto", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("muestras", sa.Integer(), nullable=False),
        sa.Column("cpu_avg", sa.Float(), nullable=False),
        sa.Column("cpu_max", sa.Integer(), nullable=False),
        sa.Column("memory_avg", sa.Float(), nullable=False),
        sa.Column("memory_max", sa.Integer(), nullable=False),
        sa.Column("disk_avg", sa.Float(), nullable=False),
        sa.Column("disk_max", sa.Integer(), nullable=False),
        sa.Column("memory_available_min", sa.BigInteger(), nullable=False),
        sa.Column("disk_used_max", sa.BigInteger(), nullable=False),
    )

    # ---------- metrics_analisis ----------
    op.create_table(
        "metrics_analisis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metricas", sa.JSON(), nullable=False),
        sa.Column("analisis", sa.JSON(), nullable=False),
    )
    op.create_index("ix_analisis_host_created", "metrics_analisis", ["host_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_analisis_host_created", table_name="metrics_analisis")
    op.drop_table("metrics_analisis")
    op.drop_table("metrics_1m")
    op.execute("DROP TABLE IF EXISTS metrics")      # borra también todas sus particiones
    op.drop_index("ix_hosts_owner_id", table_name="hosts")
    op.drop_table("hosts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
