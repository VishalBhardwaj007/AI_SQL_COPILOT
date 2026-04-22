from groq import Groq
import os
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY is missing")

client = Groq(api_key=api_key)
_cached_model = None


def _get_available_models() -> List[str]:
    models = client.models.list()
    return [m.id for m in getattr(models, "data", []) if getattr(m, "id", None)]


def _select_model(refresh: bool = False) -> str:
    global _cached_model

    env_model = os.getenv("GROQ_MODEL")
    if env_model:
        _cached_model = env_model
        return _cached_model

    if _cached_model and not refresh:
        return _cached_model

    preferred = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
    ]

    try:
        available = _get_available_models()
        for model_name in preferred:
            if model_name in available:
                _cached_model = model_name
                return _cached_model

        if available:
            _cached_model = available[0]
            return _cached_model
    except Exception:
        # Fall back to a likely-available default if model listing fails.
        pass

    _cached_model = "llama-3.3-70b-versatile"
    return _cached_model


def _schema_to_text(schema: Dict[str, List[str]]) -> str:
    if not schema:
        return "No tables found."
    lines = []
    for table, columns in schema.items():
        lines.append(f"{table}({', '.join(columns)})")
    return "\n".join(lines)


def generate_sql(user_query: str, schema: Dict[str, List[str]]) -> str:
    schema_text = _schema_to_text(schema)

    prompt = f"""
    You are an expert SQLite SQL generator.

    Database schema:
    {schema_text}

    Rules:
    - Return ONLY one valid SQLite SELECT query.
    - Use only tables and columns that exist in the schema above.
    - If needed, use LIMIT 20.
    - Do not include markdown fences.

    Query: {user_query}
    """

    model_name = _select_model()

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        error_text = str(exc).lower()
        if "decommissioned" in error_text or "model_decommissioned" in error_text:
            model_name = _select_model(refresh=True)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
        else:
            raise

    
    content = response.choices[0].message.content or ""

    if content == "":
        raise ValueError("AI returned empty response")

    print("Groq model:", model_name)
    print("AI RAW RESPONSE:", content)

    sql = content.strip()

    # clean formatting
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # keep only the SQL part from SELECT onwards if model adds extra text
    if "SELECT" in sql.upper():
        sql = sql[sql.upper().find("SELECT"):]

    if not sql.upper().startswith("SELECT"):
        raise ValueError(f"Model did not return a SELECT query: {sql}")

    return sql
