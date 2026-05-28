import os
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List

import psycopg2
import psycopg2.extras
import requests
from neo4j import GraphDatabase


PG_HOST = os.getenv("PG_HOST", "postgres14")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DATABASE = os.getenv("PG_DATABASE", "demo_data")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j-password")

FUSEKI_URL = os.getenv("FUSEKI_URL", "http://fuseki:3030").rstrip("/")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "aml").strip("/")
AML = "urn:aml:"


TABLES = {
    "Customer": ("customer", "customer_id"),
    "Account": ("account", "account_id"),
    "Transaction": ("transaction", "txn_id"),
    "Alert": ("alert", "alert_id"),
    "Case": ('"case"', "case_id"),
    "CaseNote": ("case_note", "note_id"),
    "SAR": ("sar", "sar_id"),
}


def main() -> None:
    rows = load_rows()
    sync_neo4j(rows)
    sync_fuseki(rows)
    print("Graph backend sync complete.")


def load_rows() -> Dict[str, List[Dict[str, Any]]]:
    with psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD,
    ) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            result = {}
            for label, (table, _) in TABLES.items():
                cur.execute(f"SELECT * FROM aml.{table} ORDER BY 1")
                result[label] = [dict(row) for row in cur.fetchall()]
            return result


def sync_neo4j(rows: Dict[str, List[Dict[str, Any]]]) -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            for label, (_, id_field) in TABLES.items():
                session.run(
                    f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.{id_field} IS UNIQUE"
                ).consume()
                for row in rows[label]:
                    props = neo4j_props(row)
                    session.run(
                        f"MERGE (n:{label} {{{id_field}: ${id_field}}}) SET n += $props",
                        **{id_field: props[id_field]},
                        props=props,
                    ).consume()

            relationships = [
                ("OWNS", "Customer", "customer_id", "customer_id", "Account", "account_id", "account_id", rows["Account"], "account_id"),
                ("SENT_TXN", "Account", "account_id", "from_account_id", "Transaction", "txn_id", "txn_id", rows["Transaction"], "txn_id"),
                ("TO_ACCOUNT", "Transaction", "txn_id", "txn_id", "Account", "account_id", "to_account_id", rows["Transaction"], "txn_id"),
                ("FLAGS_CUSTOMER", "Alert", "alert_id", "alert_id", "Customer", "customer_id", "primary_customer_id", rows["Alert"], "alert_id"),
                ("FLAGS_ACCOUNT", "Alert", "alert_id", "alert_id", "Account", "account_id", "primary_account_id", rows["Alert"], "alert_id"),
                ("FROM_ALERT", "Case", "case_id", "case_id", "Alert", "alert_id", "source_alert_id", rows["Case"], "case_id"),
                ("HAS_NOTE", "Case", "case_id", "case_id", "CaseNote", "note_id", "note_id", rows["CaseNote"], "note_id"),
                ("RESULTED_IN", "Case", "case_id", "case_id", "SAR", "sar_id", "sar_id", rows["SAR"], "sar_id"),
            ]
            for rel_type, from_label, from_node_key, from_row_key, to_label, to_node_key, to_row_key, rel_rows, rel_id in relationships:
                for row in rel_rows:
                    if row.get(from_row_key) is None or row.get(to_row_key) is None:
                        continue
                    session.run(
                        f"""
                        MATCH (a:{from_label} {{{from_node_key}: $from_id}})
                        MATCH (b:{to_label} {{{to_node_key}: $to_id}})
                        MERGE (a)-[r:{rel_type} {{sync_id: $sync_id}}]->(b)
                        """,
                        from_id=row[from_row_key],
                        to_id=row[to_row_key],
                        sync_id=f"{rel_type}:{row[rel_id]}",
                    ).consume()
    finally:
        driver.close()


def sync_fuseki(rows: Dict[str, List[Dict[str, Any]]]) -> None:
    wait_for_fuseki()
    update_url = f"{FUSEKI_URL}/{FUSEKI_DATASET}/update"
    response = requests.post(update_url, data={"update": "CLEAR DEFAULT"}, timeout=30)
    response.raise_for_status()

    triples: List[str] = []
    for label, (_, id_field) in TABLES.items():
        for row in rows[label]:
            subject = iri(label, row[id_field])
            triples.append(f"{subject} a <{AML}{label}> .")
            for key, value in row.items():
                if value is not None:
                    triples.append(f"{subject} <{AML}{key}> {literal(value)} .")

    triples.extend(edge_triples(rows))
    for chunk in chunks(triples, 250):
        update = "INSERT DATA {\n" + "\n".join(chunk) + "\n}"
        response = requests.post(update_url, data={"update": update}, timeout=60)
        response.raise_for_status()


def edge_triples(rows: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    triples = []
    for row in rows["Account"]:
        triples.append(f"{iri('Customer', row['customer_id'])} <{AML}OWNS> {iri('Account', row['account_id'])} .")
    for row in rows["Transaction"]:
        triples.append(f"{iri('Account', row['from_account_id'])} <{AML}SENT_TXN> {iri('Transaction', row['txn_id'])} .")
        triples.append(f"{iri('Transaction', row['txn_id'])} <{AML}TO_ACCOUNT> {iri('Account', row['to_account_id'])} .")
    for row in rows["Alert"]:
        if row.get("primary_customer_id") is not None:
            triples.append(f"{iri('Alert', row['alert_id'])} <{AML}FLAGS_CUSTOMER> {iri('Customer', row['primary_customer_id'])} .")
        if row.get("primary_account_id") is not None:
            triples.append(f"{iri('Alert', row['alert_id'])} <{AML}FLAGS_ACCOUNT> {iri('Account', row['primary_account_id'])} .")
    for row in rows["Case"]:
        if row.get("source_alert_id") is not None:
            triples.append(f"{iri('Case', row['case_id'])} <{AML}FROM_ALERT> {iri('Alert', row['source_alert_id'])} .")
    for row in rows["CaseNote"]:
        triples.append(f"{iri('Case', row['case_id'])} <{AML}HAS_NOTE> {iri('CaseNote', row['note_id'])} .")
    for row in rows["SAR"]:
        triples.append(f"{iri('Case', row['case_id'])} <{AML}RESULTED_IN> {iri('SAR', row['sar_id'])} .")
    return triples


def wait_for_fuseki() -> None:
    for _ in range(60):
        try:
            response = requests.get(f"{FUSEKI_URL}/$/ping", timeout=2)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError("Fuseki did not become ready")


def neo4j_props(row: Dict[str, Any]) -> Dict[str, Any]:
    props = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            props[key] = float(value)
        elif isinstance(value, (datetime, date)):
            props[key] = value.isoformat()
        else:
            props[key] = value
    return props


def iri(label: str, value: Any) -> str:
    return f"<{AML}{label.lower()}/{value}>"


def literal(value: Any) -> str:
    if isinstance(value, bool):
        return f'"{str(value).lower()}"^^<http://www.w3.org/2001/XMLSchema#boolean>'
    if isinstance(value, int):
        return f'"{value}"^^<http://www.w3.org/2001/XMLSchema#integer>'
    if isinstance(value, Decimal):
        return f'"{value}"^^<http://www.w3.org/2001/XMLSchema#decimal>'
    if isinstance(value, (datetime, date)):
        return f'"{value.isoformat()}"^^<http://www.w3.org/2001/XMLSchema#dateTime>'
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def chunks(values: List[str], size: int) -> Iterable[List[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


if __name__ == "__main__":
    main()
