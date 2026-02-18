import mysql.connector
import os
from utils.constants import dbCred
# -------------------------------------------------
# MySQL connection helper
# -------------------------------------------------


def get_mysql_connection(environment: str):
    """
    Return a MySQL connection using `utils.constants.dbCred`.

    Supports both shapes:
    - flat: {"host": ..., "port": ..., "user": ..., "password": ..., "database": ...}
    - nested: {"db": {...}, "ssh": {...} | None}

    SSH tunneling is **opt-in** via `ENABLE_SSH_TUNNEL=1` because containers
    typically won't have your local pem file paths available unless mounted.
    """
    env_key = (environment or "").strip().lower() or "local"
    if env_key not in dbCred:
        raise ValueError(
            f"Invalid ENRICH_ENVIRONMENT={environment!r}. Expected one of: {', '.join(dbCred.keys())}"
        )

    env_cfg = dbCred[env_key]
    # nested vs flat
    if isinstance(env_cfg, dict) and "db" in env_cfg:
        db_conf = env_cfg.get("db") or {}
        ssh_conf = env_cfg.get("ssh")
    else:
        db_conf = env_cfg
        ssh_conf = None

    if not ssh_conf:
        return mysql.connector.connect(**db_conf), None

    enable_tunnel = os.environ.get("ENABLE_SSH_TUNNEL", "0").strip().lower() in {
        "1", "true", "yes"}
    if not enable_tunnel:
        raise ValueError(
            f"SSH tunnel config present for env={env_key!r} but tunneling is disabled. "
            f"Set ENABLE_SSH_TUNNEL=1 and mount/provide SSH credentials if you want this to run."
        )

    # Import only when needed (keeps local/dev startup lighter)
    from sshtunnel import SSHTunnelForwarder  # type: ignore

    # Allow overriding SSH settings via env (recommended for containers)
    ssh_host = (os.environ.get("SSH_HOST")
                or ssh_conf.get("ssh_host") or "").strip()
    ssh_port = int(os.environ.get("SSH_PORT") or ssh_conf.get("ssh_port", 22))
    ssh_user = (os.environ.get("SSH_USER")
                or ssh_conf.get("ssh_user") or "").strip()

    # Prefer env override; otherwise use config value
    pem_path = os.environ.get("SSH_PKEY_PATH") or ssh_conf.get("pem_file")
    ssh_password = os.environ.get("SSH_PASSWORD")

    ssh_pkey = pem_path if pem_path and os.path.isfile(pem_path) else None
    if not ssh_pkey and not ssh_password:
        raise ValueError(
            "No SSH credentials available for tunnel (no readable pem key and no SSH_PASSWORD). "
            "Mount a pem into the container and set SSH_PKEY_PATH, or set SSH_PASSWORD."
        )

    if not ssh_host or not ssh_user:
        raise ValueError(
            f"Missing SSH gateway settings (SSH_HOST={ssh_host!r}, SSH_USER={ssh_user!r}). "
            "Set SSH_HOST/SSH_PORT/SSH_USER env vars (or fill them in dbCred[env]['ssh'])."
        )

    remote_db_host = (os.environ.get("REMOTE_DB_HOST") or ssh_conf.get(
        "remote_db_host") or "127.0.0.1").strip()
    remote_db_port = int(os.environ.get("REMOTE_DB_PORT")
                         or ssh_conf.get("remote_db_port", 3306))

    tunnel = SSHTunnelForwarder(
        (ssh_host, ssh_port),
        ssh_username=ssh_user,
        ssh_pkey=ssh_pkey,
        ssh_password=ssh_password,
        allow_agent=False,
        host_pkey_directories=[],
        remote_bind_address=(
            remote_db_host,
            remote_db_port,
        ),
    )
    try:
        tunnel.start()
    except Exception as e:
        raise ValueError(
            f"Could not establish SSH tunnel to {ssh_host}:{ssh_port} as {ssh_user!r} "
            f"(remote db {remote_db_host}:{remote_db_port}): {e}"
        ) from e

    connection = mysql.connector.connect(
        host="127.0.0.1",
        port=tunnel.local_bind_port,
        user=db_conf.get("user"),
        password=db_conf.get("password"),
        database=db_conf.get("database"),
    )
    return connection, tunnel
