"""
Chart type suggestion and Apache ECharts option generation for graph query results.

Uses the same LLM (OpenAI) as nl_to_cypher to:
1. Decide result presentation: table_only, table_and_graph, or table_and_traditional (bar/line/pie).
2. When a chart is needed, generate ECharts option JSON from the query context and result data.

Chart types:
- table_only: no chart, HTML table only.
- table_and_graph: table plus ECharts graph series (nodes and relationships).
- table_and_traditional: table plus bar, line, or pie chart.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Max rows to send to LLM for chart data (avoid token overflow)
_MAX_ROWS_FOR_CHART = 100


def _llm_client() -> Optional[Any]:
    """Return OpenAI client if API key is set and library available."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or not OPENAI_AVAILABLE:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL")
    client_kw: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kw["base_url"] = base_url
    return openai.OpenAI(**client_kw)


def _model_for_chart() -> str:
    """Model for chart suggestion and ECharts generation. Prefer OPENAI_MODEL_CHART, then CYPHER, then OPENAI_MODEL."""
    return (
        os.environ.get("OPENAI_MODEL_CHART", "").strip()
        or os.environ.get("OPENAI_MODEL_CYPHER", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _normalize_columns(columns: Any) -> List[str]:
    """Return list of column names from PuppyGraph-style columns (strings or objects with name)."""
    if not columns or not isinstance(columns, list):
        return []
    names: List[str] = []
    for c in columns:
        if isinstance(c, str):
            names.append(c)
        elif isinstance(c, dict) and c.get("name") is not None:
            names.append(str(c["name"]))
        else:
            names.append(str(c))
    return names


def _rows_from_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract list of row dicts from PuppyGraph result shape { results, columns } or array."""
    if isinstance(data, list):
        return data[: _MAX_ROWS_FOR_CHART]
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        if isinstance(results, list):
            return results[:_MAX_ROWS_FOR_CHART]
    return []


def _columns_from_data(data: Dict[str, Any]) -> List[str]:
    """Extract column names from PuppyGraph result."""
    if isinstance(data, dict) and "columns" in data:
        return _normalize_columns(data["columns"])
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return list(data[0].keys())
    return []


def _sanitize_for_json(obj: Any) -> Any:
    """Make object JSON-serializable (dates, etc.)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "iso_format"):
        return str(obj.iso_format())
    return str(obj)


def _fallback_bar_chart_option(
    columns: List[str],
    rows: List[Dict[str, Any]],
    user_query: Optional[str] = None,
    series_type: str = "bar",
) -> Optional[Dict[str, Any]]:
    """Build a minimal ECharts bar or line option from result columns and rows when LLM does not return one.
    series_type: 'bar' or 'line' (pie uses category-count only and stays bar-like for now).
    """
    if not columns or not rows:
        return None
    if series_type not in ("bar", "line"):
        series_type = "bar"
    query_lower = (user_query or "").lower()
    # "Bar chart of X types" or "X by type" -> count by a categorical column (e.g. alert_type)
    category_count = _fallback_category_count_chart(columns, rows, user_query)
    if category_count is not None:
        if series_type == "line" and category_count.get("series"):
            category_count = dict(category_count)
            category_count["series"] = [{**category_count["series"][0], "type": "line"}]
        return category_count
    # Prefer a column named amount, value, count, or first numeric-looking column for series data
    numeric_candidates = ["amount", "value", "count", "total", "sum", "txn_id"]
    value_col: Optional[str] = None
    for cand in numeric_candidates:
        if cand in columns:
            value_col = cand
            break
    if not value_col:
        for col in columns:
            if not rows:
                continue
            val = rows[0].get(col)
            if val is not None and isinstance(val, (int, float)):
                value_col = col
                break
    if not value_col:
        return None
    # Label column: first column that isn't the value column, or use value_col labels (e.g. "Txn 1")
    label_col: Optional[str] = None
    for col in columns:
        if col != value_col:
            label_col = col
            break
    labels = []
    values = []
    for i, row in enumerate(rows[:50]):
        v = row.get(value_col)
        if v is not None and isinstance(v, (int, float)):
            values.append(round(float(v), 2))
        else:
            values.append(0)
        if label_col is not None and row.get(label_col) is not None:
            labels.append(str(row[label_col])[:30])
        else:
            labels.append(str(value_col) + " " + str(i + 1))
    return {
        "title": {"text": "Transaction amounts" if value_col == "amount" else value_col.replace("_", " ").title()},
        "tooltip": {},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value"},
        "series": [{"type": series_type, "data": values}],
    }


def _fallback_category_count_chart(
    columns: List[str], rows: List[Dict[str, Any]], user_query: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Build a bar chart by counting rows per category (e.g. alert_type). Use when user asks for 'bar chart of X types'."""
    if not columns or not rows:
        return None
    query_lower = (user_query or "").lower()
    # Prefer a column that looks like a category: exact name or column ending in _type, or string column
    category_candidates = ["alert_type", "type", "status", "severity", "category", "channel", "risk_rating"]
    category_col: Optional[str] = None
    for cand in category_candidates:
        if cand in columns:
            category_col = cand
            break
    if not category_col:
        for col in columns:
            # Prefixed names from Cypher (e.g. a0.alert_type)
            if col.endswith("_type") or ".alert_type" in col or col.endswith(".type") or "alert_type" in col:
                category_col = col
                break
    if not category_col and ("types" in query_lower or "by type" in query_lower or "by status" in query_lower):
        for col in columns:
            val = rows[0].get(col) if rows else None
            if val is not None and isinstance(val, str):
                category_col = col
                break
    if not category_col:
        return None
    counts: Dict[str, int] = {}
    for row in rows:
        val = row.get(category_col)
        key = str(val) if val is not None else "(empty)"
        counts[key] = counts.get(key, 0) + 1
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    title = (user_query or "Count by " + category_col).replace("_", " ").title()
    if len(title) > 60:
        title = "Count by " + category_col.replace("_", " ").title()
    return {
        "title": {"text": title},
        "tooltip": {},
        "xAxis": {"type": "category", "data": labels},
        "yAxis": {"type": "value", "name": "Count"},
        "series": [{"type": "bar", "data": values}],
    }


def suggest_chart_and_echarts(
    user_query_or_cypher: str,
    data: Dict[str, Any],
    is_natural_language: bool = False,
) -> Dict[str, Any]:
    """
    Decide chart type and generate ECharts option from query and result data.

    Args:
        user_query_or_cypher: The natural language question or the Cypher query text.
        data: Query result: { results: [...], columns: [...] } or list of row dicts.
        is_natural_language: True if user_query_or_cypher is natural language (helps LLM context).

    Returns:
        {
            "chart_type": "table_only" | "table_and_graph" | "table_and_traditional",
            "chart_subtype": null | "bar" | "line" | "pie",
            "echarts_option": null | { ... }  # full ECharts option when chart is needed
        }
    """
    default_result: Dict[str, Any] = {
        "chart_type": "table_only",
        "chart_subtype": None,
        "echarts_option": None,
    }
    columns = _columns_from_data(data)
    rows = _rows_from_data(data)
    if not columns and not rows:
        return default_result

    query_lower = (user_query_or_cypher or "").lower()
    client = _llm_client()
    if not client:
        # No LLM: try fallback when user asked for a chart, or when result is chartable (e.g. Execute Graph Query with Cypher)
        subtype = "bar" if "bar chart" in query_lower else ("pie" if "pie chart" in query_lower else "line")
        fallback = _fallback_bar_chart_option(
            columns, rows, user_query_or_cypher, series_type="line" if subtype == "line" else "bar"
        )
        if fallback:
            return {
                "chart_type": "table_and_traditional",
                "chart_subtype": subtype,
                "echarts_option": fallback,
            }
        return default_result

    # Build a small sample for the LLM (first N rows, sanitized)
    sample = _sanitize_for_json(rows[:50])
    query_label = "Natural language question" if is_natural_language else "Cypher query"
    data_preview = json.dumps({"columns": columns, "rows": sample}, indent=2)

    system = (
        "You are a chart and visualization advisor for graph query results. "
        "Given the user's question or Cypher query and the result columns and sample rows, "
        "you must respond with a single JSON object (no markdown, no code fence) with exactly these keys:\n"
        '- "chart_type": one of "table_only", "table_and_graph", "table_and_traditional"\n'
        '- "chart_subtype": if chart_type is "table_and_traditional", one of "bar", "line", "pie"; otherwise null\n'
        '- "echarts_option": if chart_type is not "table_only", a complete Apache ECharts option object (a JSON object, not a string) ready for echarts.init().setOption(); otherwise null\n\n'
        "CRITICAL - Honor explicit chart type in the user's question:\n"
        '- If the user says "line chart" or "show me a line chart", you MUST set chart_subtype to "line" and echarts_option.series[].type to "line" (not bar).\n'
        '- If the user says "pie chart", you MUST set chart_subtype to "pie" and use series type "pie".\n'
        '- If the user says "bar chart", use chart_subtype "bar" and series type "bar".\n\n'
        "Rules:\n"
        "- If the user explicitly asks for a chart (e.g. 'bar chart of', 'show me a line chart', 'graph of relationships'), you MUST return that chart type and provide a complete echarts_option object. Do not return table_only when the user asked for a chart.\n"
        "- table_only: use only when the result is best shown as a table and the user did not ask for any chart.\n"
        "- table_and_graph: use when the result clearly represents nodes and relationships or the user asked for a graph/network view. "
        "For echarts_option use series type \"graph\" with nodes (id, name, category) and links (source, target).\n"
        "- table_and_traditional: use when the result has clear categorical and numeric columns (e.g. amounts, counts, time series) or the user asked for a bar/line/pie chart. "
        "When the user says 'line chart' or data has time/order (e.g. timestamp, amount over rows), use series type \"line\" with xAxis.data and series[].data. "
        "When the user says 'bar chart' or categories with values, use series type \"bar\". When the user says 'pie chart' or proportions, use series type \"pie\". "
        "ECharts option must be a valid JSON object: include title (text), tooltip, and series (array of objects with type and data). Never return echarts_option as a string; always an object."
    )
    user = (
        f"{query_label}:\n{user_query_or_cypher[:2000]}\n\n"
        f"Result data (columns and sample rows):\n{data_preview}\n\n"
        "Respond with a single JSON object only (chart_type, chart_subtype, echarts_option)."
    )
    try:
        response = client.chat.completions.create(
            model=_model_for_chart(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        content = (response.choices[0].message.content or "").strip()
        # Strip markdown code block if present (e.g. ```json ... ``` or ``` ... ```)
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            # Remove optional language tag on first line (e.g. "json")
            if lines and lines[0].strip().lower() in ("json", "javascript"):
                lines = lines[1:]
            content = "\n".join(lines)
        out = json.loads(content)
        chart_type = out.get("chart_type") or "table_only"
        if chart_type not in ("table_only", "table_and_graph", "table_and_traditional"):
            chart_type = "table_only"
        chart_subtype = out.get("chart_subtype")
        if chart_type != "table_and_traditional":
            chart_subtype = None
        elif chart_subtype not in ("bar", "line", "pie"):
            chart_subtype = "bar"
        echarts_option = out.get("echarts_option")
        if chart_type == "table_only":
            echarts_option = None
        if echarts_option is not None and not isinstance(echarts_option, dict):
            # LLM sometimes returns echarts_option as a JSON string; parse it
            if isinstance(echarts_option, str):
                try:
                    echarts_option = json.loads(echarts_option)
                except json.JSONDecodeError:
                    logger.warning("Chart suggestion: echarts_option was string but not valid JSON")
                    echarts_option = None
            else:
                echarts_option = None
        if chart_type != "table_only" and echarts_option is None:
            logger.warning("Chart suggestion: chart_type=%s but echarts_option missing or invalid", chart_type)
        # Fallback: user explicitly asked for a chart but LLM didn't provide one
        if "bar chart" in query_lower or "pie chart" in query_lower or "line chart" in query_lower:
            if chart_type == "table_only" or echarts_option is None:
                subtype = "bar" if "bar chart" in query_lower else ("pie" if "pie chart" in query_lower else "line")
                fallback = _fallback_bar_chart_option(
                    columns, rows, user_query_or_cypher, series_type="line" if subtype == "line" else "bar"
                )
                if fallback:
                    chart_type = "table_and_traditional"
                    chart_subtype = subtype
                    echarts_option = fallback
                    logger.info("Chart suggestion: using fallback %s chart (user asked for chart)", subtype)
        # Data-driven fallback: when result has chartable structure (e.g. category or numeric column), show a chart even when query was Cypher
        if chart_type == "table_only" and columns and rows:
            subtype_fallback = "line" if "line chart" in query_lower else "bar"
            fallback = _fallback_bar_chart_option(
                columns, rows, user_query_or_cypher, series_type=subtype_fallback
            )
            if fallback:
                chart_type = "table_and_traditional"
                chart_subtype = subtype_fallback
                echarts_option = fallback
                logger.info("Chart suggestion: using data-driven fallback (chartable result)")
        return {
            "chart_type": chart_type,
            "chart_subtype": chart_subtype,
            "echarts_option": echarts_option,
        }
    except json.JSONDecodeError as e:
        logger.warning("Chart suggestion LLM response was not valid JSON: %s", e)
        if columns and rows:
            subtype = "line" if "line chart" in query_lower else "bar"
            fallback = _fallback_bar_chart_option(columns, rows, user_query_or_cypher, series_type="line" if subtype == "line" else "bar")
            if fallback:
                return {"chart_type": "table_and_traditional", "chart_subtype": subtype, "echarts_option": fallback}
        return default_result
    except Exception as e:
        logger.warning("Chart suggestion failed: %s", e)
        if columns and rows:
            subtype = "line" if "line chart" in query_lower else "bar"
            fallback = _fallback_bar_chart_option(columns, rows, user_query_or_cypher, series_type="line" if subtype == "line" else "bar")
            if fallback:
                return {"chart_type": "table_and_traditional", "chart_subtype": subtype, "echarts_option": fallback}
        return default_result
