# Natural Language Graph Query (NLI)

The Graph Query UI supports natural language questions that are converted to Cypher, validated against the PuppyGraph schema and execution engine, and executed.

## Workflow (LLM with schema JSON, then validate and retry)

1. **Schema** – The backend fetches the current graph schema from PuppyGraph (`/schemajson`).
2. **Credential redaction** – Before sending the schema to the LLM, credentials are redacted (e.g. `password`, `username`, `jdbcUri`, `secret`, `api_key`, `token`). Values are replaced with `[REDACTED]`.
3. **Cypher generation (LLM)** – When `OPENAI_API_KEY` is set, the **LLM** receives the **redacted schema JSON** and the **user's question**. It generates a single openCypher (v9) statement. No rule-based extraction is used for the LLM path.
4. **Validation** – Every generated Cypher (from LLM or rules) is validated so it is fully supported by the schema and PuppyGraph:
   Labels, relationships, and property references are checked; if invalid, the LLM is retried once with the validation errors.
5. **LLM retry** – (Covered in step 4: one retry with validation errors.)
6. **Rule-based fallback** – If the LLM is unavailable or still invalid after retry, **rule-based** analysis and Cypher generation is used.
7. **Optional PuppyGraph dry run** – The API accepts `validate_with_puppygraph: true`; when set, execution errors from PuppyGraph are returned as validation errors.
8. **Execution** – If the user chose “Ask & Execute”, the query is authorized by Cerbos and run on PuppyGraph.

## Optional LLM (OpenAI)

For best quality and complex phrasing, set **`OPENAI_API_KEY`** so the backend uses the LLM first. Rule-based generation is used only when the LLM is unavailable or returns invalid Cypher after one retry.

### Setup

1. **Install** – The backend `requirements.txt` includes `openai>=1.0.0`. Rebuild the backend image or install in your venv.
2. **Configure** – Set in `.env` or the environment of the backend process:
   - **`OPENAI_API_KEY`** (required for LLM) – Your OpenAI API key.
   - **`OPENAI_MODEL`** (optional) – Default model for most LLM calls; default `gpt-4o-mini`.
   - **`OPENAI_MODEL_CYPHER`** (optional) – Model used only for natural-language-to-Cypher generation (e.g. a stronger 5.2 model). If unset, falls back to `OPENAI_MODEL` then `gpt-4o-mini`.
   - **`OPENAI_BASE_URL`** (optional) – Override API base URL (e.g. Azure or custom endpoint).

Example `.env`:

```bash
OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o-mini
# OPENAI_MODEL_CYPHER=gpt-4.2
# OPENAI_BASE_URL=
```

3. **Restart** – Restart the policy-registry backend so it picks up the new env (e.g. `docker compose up -d --build policy-registry-backend` with the env in `compose.yml` or `.env`).

### Behavior

- **Schema + query to LLM**: The backend sends the full (redacted) schema as JSON and the user's question to the LLM. No hand-built schema summary or rule-based extraction is used for the LLM; the model infers Cypher from the schema structure and the question.
- **Redaction**: Fields such as `password`, `username`, `jdbcUri`, `secret`, `api_key`, and `token` in the schema are replaced with `[REDACTED]` before the schema is sent to the LLM.
- **Validation then retry**: Generated Cypher is validated (labels, relationships, properties). If invalid, the LLM is called once more with the validation errors and the same schema + question.
- **Fallback**: If the LLM is unavailable or still invalid after retry, rule-based generation runs. The same validations apply to rule-based Cypher.
- **PuppyGraph compatibility**: Use `validate_with_puppygraph: true` in the natural-language request body to run the query against PuppyGraph and surface execution errors as validation errors.

## Example complex queries

You can try these in the **Graph Query** tab (“Or ask in natural language”). The system converts them to Cypher using the current PuppyGraph schema (entities, relationships, and numeric filters are schema-driven). Run `just nl-queries` to see rule-based output for these against the AML schema.

### Single-entity and filters

| Natural language | Typical Cypher (rule-based) |
|------------------|-----------------------------|
| Show me all customers | `MATCH (c0:Customer) RETURN c0.customer_id, c0.name, ... LIMIT 25` |
| Transactions over 100000 | `MATCH (t0:Transaction) WHERE t0.amount > 100000 RETURN t0.txn_id, t0.amount, ... LIMIT 25` |
| Transactions over 50000 | `MATCH (t0:Transaction) WHERE t0.amount > 50000 RETURN ... LIMIT 25` |
| Top 10 customers by risk | `MATCH (c0:Customer) RETURN c0.customer_id, c0.name, ... LIMIT 10` |

### Paths (entities + relationships)

| Natural language | Typical Cypher (rule-based) |
|------------------|-----------------------------|
| Customers who own accounts that sent transactions over 50000 | `MATCH (t0:Transaction) WHERE t0.amount > 50000 RETURN t0.txn_id, t0.amount, ... LIMIT 25` |
| Find accounts that received transactions | `MATCH (t0:Transaction) RETURN t0.txn_id, t0.from_account_id, ... LIMIT 25` |
| List alerts that flag customers | `MATCH (c0:Customer) RETURN c0.customer_id, c0.name, ... LIMIT 25` |
| Show cases that have notes | `MATCH (c0:Case) RETURN c0.case_id, c0.status, ... LIMIT 25` |
| How many customers own accounts? | `MATCH (c0:Customer) RETURN c0.customer_id, c0.name, ... LIMIT 25` |

### Phrasing tips

- **Entities**: Use schema vertex names or common plurals (e.g. “customers”, “transactions”, “accounts”, “alerts”, “cases”).
- **Relationships**: Use phrases that describe the edge, e.g. “own accounts”, “sent transaction”, “flags customer”, “has note”, “from alert”, “resulted in SAR”.
- **Numeric filters**: “over N”, “above N”, “greater than N”, or “amount over N” map to schema numeric attributes (e.g. `amount` on `Transaction`).
- **Limit**: “Top 10”, “first 5”, “limit 20” set the result limit.

For more Cypher patterns (including multi-hop and aggregation), see [AML_CYPHER_EXAMPLES.md](./AML_CYPHER_EXAMPLES.md). The NLI rule-based path produces single-path or single-vertex Cypher; the **LLM** path (with `OPENAI_API_KEY` set) can handle more varied phrasing and sometimes more complex patterns.

## Analyst query examples

These are natural language questions an AML analyst might ask in the **Graph Query** tab. They map to common workflows: customer/risk screening, transaction monitoring, alert and case investigation, and SAR-related checks. Authorization still applies (see [AML_USER_CREDENTIALS.md](./AML_USER_CREDENTIALS.md)).

### Customer and risk screening

| What an analyst might ask | Use in NLI |
|---------------------------|------------|
| Show me all customers | ✅ |
| Customers with high risk | ✅ (may need LLM for `risk_rating = 'high'`) |
| List PEP customers / politically exposed persons | ✅ (may need LLM for `pep_flag = true`) |
| Top 10 customers by risk | ✅ |
| How many customers own accounts? | ✅ |

### Transaction monitoring

| What an analyst might ask | Use in NLI |
|---------------------------|------------|
| Transactions over 50000 | ✅ |
| Transactions over 100000 | ✅ |
| High-value transactions | ✅ (LLM can map to amount threshold) |
| Customers who own accounts that sent transactions over 50000 | ✅ |
| Find accounts that received transactions | ✅ |
| Transactions from account to account | ✅ (TO_ACCOUNT-style path; LLM may help) |

### Alerts and cases

| What an analyst might ask | Use in NLI |
|---------------------------|------------|
| List alerts that flag customers | ✅ |
| Alerts that flag accounts | ✅ |
| Show cases that have notes | ✅ |
| Cases from alert | ✅ (FROM_ALERT) |
| Cases that resulted in SAR | ✅ (RESULTED_IN) |

### Investigation and linkage

| What an analyst might ask | Use in NLI |
|---------------------------|------------|
| Show me all alerts | ✅ |
| Show me all cases | ✅ |
| Show me all SARs | ✅ |
| Case notes for a case | ✅ (HAS_NOTE; may need specific case_id in Cypher) |

**Tips for analysts**

- Use **natural language** for quick checks: “transactions over 50000”, “customers who own accounts”, “alerts that flag customers”.
- For **exact filters** (e.g. `risk_rating = 'high'`, `customer_id: 1`), either try the NLI with a clear phrase or use the **openCypher** box and paste a query from [AML_CYPHER_EXAMPLES.md](./AML_CYPHER_EXAMPLES.md).
- **Cerbos** enforces role and clearance (e.g. junior vs senior analyst, PEP access, transaction thresholds); the same NLI query can be allowed for one user and denied for another.

To run the analyst query set from the repo: `just nl-queries-analyst`.
