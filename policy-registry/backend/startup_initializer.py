import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from trino_client import get_trino_client

logger = logging.getLogger(__name__)

_INIT_STATUS: Dict[str, Any] = {
    "state": "pending",
    "last_run": None,
    "error": None,
}


ICEBERG_STATEMENTS: List[Tuple[str, str]] = [
    ("Create Iceberg demo schema", "CREATE SCHEMA IF NOT EXISTS iceberg.demo"),
    ("Create Iceberg sales schema", "CREATE SCHEMA IF NOT EXISTS iceberg.sales"),
    ("Reset Iceberg sales person table", "DROP TABLE IF EXISTS iceberg.sales.person"),
    (
        "Create Iceberg sales person table",
        """
        CREATE TABLE iceberg.sales.person (
            id bigint,
            first_name varchar,
            last_name varchar,
            job_title varchar,
            age integer
        )
        """,
    ),
    (
        "Seed Iceberg sales person table",
        """
        INSERT INTO iceberg.sales.person (id, first_name, last_name, job_title, age) VALUES
        (1, 'Alex', 'Thompson', 'Data Scientist', 28),
        (2, 'Maria', 'Gonzalez', 'Frontend Developer', 31),
        (3, 'James', 'Lee', 'Backend Developer', 29),
        (4, 'Sophia', 'Chen', 'Machine Learning Engineer', 26),
        (5, 'Daniel', 'White', 'Cloud Architect', 34),
        (6, 'Olivia', 'Harris', 'Security Engineer', 27),
        (7, 'William', 'Clark', 'Database Administrator', 33),
        (8, 'Ava', 'Lewis', 'Network Engineer', 25),
        (9, 'Ethan', 'Robinson', 'Site Reliability Engineer', 30),
        (10, 'Isabella', 'Walker', 'Technical Writer', 32)
        """,
    ),
    (
        "Reset Iceberg employee performance table",
        "DROP TABLE IF EXISTS iceberg.demo.employee_performance",
    ),
    (
        "Create Iceberg employee performance table",
        """
        CREATE TABLE iceberg.demo.employee_performance (
            employee_id bigint,
            performance_score decimal(5,2),
            projects_completed integer,
            department varchar
        )
        """,
    ),
    (
        "Seed Iceberg employee performance table",
        """
        INSERT INTO iceberg.demo.employee_performance
            (employee_id, performance_score, projects_completed, department) VALUES
        (1, 4.2, 8, 'Engineering'),
        (2, 3.8, 6, 'Engineering'),
        (3, 4.5, 10, 'Engineering'),
        (4, 4.1, 7, 'Data Science'),
        (5, 3.9, 5, 'Infrastructure'),
        (6, 4.0, 6, 'Security'),
        (7, 3.7, 4, 'Database'),
        (8, 4.3, 9, 'Network'),
        (9, 4.4, 8, 'Reliability'),
        (10, 3.6, 5, 'Documentation')
        """,
    ),
]


def get_startup_init_status() -> Dict[str, Any]:
    return dict(_INIT_STATUS)


def _execute(query: str) -> None:
    trino_client = get_trino_client()
    with trino_client.execute_query("startup", "iceberg", "information_schema", query) as (
        success,
        _data,
        _columns,
        error,
    ):
        if not success:
            raise RuntimeError(error or "Trino query failed")


def ensure_iceberg_demo_data(max_attempts: int = 8, delay_seconds: int = 5) -> None:
    _INIT_STATUS.update({
        "state": "running",
        "last_run": datetime.utcnow().isoformat() + "Z",
        "error": None,
    })

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            for label, statement in ICEBERG_STATEMENTS:
                logger.info("Startup data init: %s", label)
                _execute(statement)

            _execute("SELECT COUNT(*) FROM iceberg.sales.person")
            _execute("SELECT COUNT(*) FROM iceberg.demo.employee_performance")
            _INIT_STATUS.update({
                "state": "ready",
                "last_run": datetime.utcnow().isoformat() + "Z",
                "error": None,
            })
            logger.info("Startup data init completed")
            return
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Startup data init attempt %s/%s failed: %s",
                attempt,
                max_attempts,
                last_error,
            )
            if attempt < max_attempts:
                time.sleep(delay_seconds)

    _INIT_STATUS.update({
        "state": "failed",
        "last_run": datetime.utcnow().isoformat() + "Z",
        "error": last_error,
    })
    raise RuntimeError(f"Startup data init failed: {last_error}")
