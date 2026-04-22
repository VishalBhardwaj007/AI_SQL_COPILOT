from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
from pydantic import BaseModel
import hashlib
import hmac
import sqlite3
import pandas as pd
from io import StringIO, BytesIO
from pathlib import Path
import re
import secrets
from ai import generate_sql
from forecasting import forecast_values

app = FastAPI()


class Query(BaseModel):
    user_query: str


class AuthRequest(BaseModel):
    username: str
    password: str


def get_db_connection():
    return sqlite3.connect("database.db")


def init_auth_tables() -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES app_users(id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_user_tables (
                user_id INTEGER NOT NULL,
                logical_name TEXT NOT NULL,
                physical_name TEXT NOT NULL UNIQUE,
                source_file TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, logical_name),
                FOREIGN KEY(user_id) REFERENCES app_users(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


init_auth_tables()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120_000,
    ).hex()


def require_valid_auth_input(username: str, password: str) -> None:
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO app_sessions (token, user_id) VALUES (?, ?)",
            (token, user_id),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token.")

    token = authorization.removeprefix("Bearer ").strip()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT app_users.id, app_users.username
            FROM app_sessions
            JOIN app_users ON app_users.id = app_sessions.user_id
            WHERE app_sessions.token = ?
            """,
            (token,),
        )
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        return dict(user)
    finally:
        conn.close()


def get_user_id(user: dict) -> int:
    return int(user["id"])


def physical_table_name(user_id: int, logical_name: str) -> str:
    return f"user_{user_id}__{logical_name}"


def get_user_tables(user_id: int) -> list[dict]:
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT logical_name, physical_name, source_file
            FROM app_user_tables
            WHERE user_id = ?
            ORDER BY logical_name
            """,
            (user_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_schema(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        schema = {}
        for table in get_user_tables(user_id):
            cursor.execute(f"PRAGMA table_info({quote_identifier(table['physical_name'])})")
            columns = [row[1] for row in cursor.fetchall()]
            schema[table["logical_name"]] = columns

        return schema
    finally:
        conn.close()


def get_physical_table_name(user_id: int, logical_name: str) -> str | None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT physical_name
            FROM app_user_tables
            WHERE user_id = ? AND logical_name = ?
            """,
            (user_id, logical_name),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def reject_cross_user_sql(query: str) -> None:
    if re.search(r"\b(app_[a-z0-9_]*|user_\d+__\w+)\b", query, flags=re.IGNORECASE):
        raise ValueError("Queries can only use your uploaded table names.")


def run_query(query: str, user_id: int):
    reject_cross_user_sql(query)
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        for table in get_user_tables(user_id):
            cursor.execute(
                f"""
                CREATE TEMP VIEW {quote_identifier(table["logical_name"])}
                AS SELECT * FROM {quote_identifier(table["physical_name"])}
                """
            )

        cursor.execute(query)

        if cursor.description is not None:
            rows = [dict(row) for row in cursor.fetchall()]
            return {"rows": rows, "row_count": len(rows)}

        conn.commit()
        return {"rows": [], "row_count": 0}

    except Exception as e:
        return {"error": str(e)}

    finally:
        conn.close()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def table_name_from_filename(filename: str | None) -> str:
    stem = Path(filename or "uploaded_data").stem.lower()
    table_name = re.sub(r"[^a-z0-9_]+", "_", stem).strip("_")

    if not table_name:
        table_name = "uploaded_data"
    if table_name[0].isdigit():
        table_name = f"table_{table_name}"

    return table_name


def read_upload_dataframe(file: UploadFile, contents: bytes) -> pd.DataFrame:
    if file.filename and file.filename.lower().endswith(".csv"):
        try:
            return pd.read_csv(StringIO(contents.decode("utf-8")))
        except Exception:
            return pd.read_csv(StringIO(contents.decode("latin-1")))

    return pd.read_excel(BytesIO(contents))


def get_table_names(user_id: int) -> list[str]:
    return [table["logical_name"] for table in get_user_tables(user_id)]


@app.get("/")
def home():
    return {"message": "AI Data Pipeline Running"}


@app.post("/auth/signup")
def signup(request: AuthRequest):
    username = request.username.strip()
    require_valid_auth_input(username, request.password)

    salt = secrets.token_hex(16)
    password_hash = hash_password(request.password, salt)
    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO app_users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username, password_hash, salt),
        )
        conn.commit()
        user_id = cursor.lastrowid
        if user_id is None:
            raise HTTPException(status_code=500, detail="Could not create user account.")
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists.")
    finally:
        conn.close()

    token = create_session(user_id)
    return {"message": "Account created", "username": username, "access_token": token}


@app.post("/auth/login")
def login(request: AuthRequest):
    username = request.username.strip()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, salt FROM app_users WHERE username = ?",
            (username,),
        )
        user = cursor.fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    candidate_hash = hash_password(request.password, user["salt"])
    if not hmac.compare_digest(candidate_hash, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_session(int(user["id"]))
    return {"message": "Logged in", "username": user["username"], "access_token": token}


@app.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return {"message": "Logged out"}

    token = authorization.removeprefix("Bearer ").strip()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM app_sessions WHERE token = ?", (token,))
        conn.commit()
    finally:
        conn.close()

    return {"message": "Logged out"}


@app.get("/schema")
def schema(user: dict = Depends(get_current_user)):
    return {"schema": get_schema(get_user_id(user))}


@app.get("/tables")
def list_tables(user: dict = Depends(get_current_user)):
    try:
        user_id = get_user_id(user)
        schema_map = get_schema(user_id)
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            tables = []
            for table in get_user_tables(user_id):
                logical_name = table["logical_name"]
                physical_name = table["physical_name"]
                columns = schema_map[logical_name]
                cursor.execute(f"SELECT COUNT(*) FROM {quote_identifier(physical_name)}")
                row_count = cursor.fetchone()[0]
                tables.append(
                    {
                        "table": logical_name,
                        "columns": columns,
                        "column_count": len(columns),
                        "rows": row_count,
                    }
                )
        finally:
            conn.close()

        return {"tables": tables}
    except Exception as e:
        return {"error": str(e)}


@app.get("/tables/{table_name}/preview")
def preview_table(
    table_name: str,
    limit: int = 100,
    user: dict = Depends(get_current_user),
):
    try:
        if limit < 1:
            limit = 1
        if limit > 500:
            limit = 500

        user_id = get_user_id(user)
        physical_name = get_physical_table_name(user_id, table_name)
        if physical_name is None:
            return {"error": f"Table not found: {table_name}"}

        conn = get_db_connection()
        try:
            df = pd.read_sql_query(
                f"SELECT * FROM {quote_identifier(physical_name)} LIMIT ?",
                conn,
                params=(limit,),
            )
        finally:
            conn.close()

        return {
            "table": table_name,
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records"),
            "row_count": len(df),
            "limit": limit,
        }
    except Exception as e:
        return {"error": str(e)}


@app.delete("/tables/{table_name}")
def delete_table(table_name: str, user: dict = Depends(get_current_user)):
    try:
        user_id = get_user_id(user)
        physical_name = get_physical_table_name(user_id, table_name)
        if physical_name is None:
            return {"error": f"Table not found: {table_name}"}

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE {quote_identifier(physical_name)}")
            cursor.execute(
                "DELETE FROM app_user_tables WHERE user_id = ? AND logical_name = ?",
                (user_id, table_name),
            )
            conn.commit()
        finally:
            conn.close()

        return {"message": f"Table `{table_name}` removed", "table": table_name}
    except Exception as e:
        return {"error": str(e)}


@app.post("/query")
def query_db(query: Query, user: dict = Depends(get_current_user)):
    try:
        user_id = get_user_id(user)
        schema_map = get_schema(user_id)
        if not schema_map:
            return {"error": "No tables found. Upload a CSV/Excel file first."}

        sql = generate_sql(query.user_query, schema_map)
        result = run_query(sql, user_id)

        if "error" in result:
            return {
                "input": query.user_query,
                "sql": sql,
                "error": result["error"],
            }

        return {
            "input": query.user_query,
            "sql": sql,
            "rows": result["rows"],
            "row_count": result["row_count"],
        }

    except Exception as e:
        return {"error": str(e)}


@app.get("/forecast/sales")
def forecast_sales(periods: int = 5, user: dict = Depends(get_current_user)):
    try:
        if periods < 1:
            return {"error": "periods must be at least 1"}

        user_id = get_user_id(user)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            tables = get_user_tables(user_id)

            if not tables:
                return {"error": "No uploaded tables found. Upload a CSV/Excel file first."}

            selected_logical_table = None
            selected_physical_table = None
            date_col = None
            value_col = None

            for table in tables:
                cursor.execute(f"PRAGMA table_info({quote_identifier(table['physical_name'])})")
                columns = [row[1] for row in cursor.fetchall()]
                candidate_value_col = next(
                    (
                        col
                        for target in ["amount", "sales", "revenue", "total", "qty"]
                        for col in columns
                        if col.lower().strip() == target
                    ),
                    None,
                )

                if candidate_value_col:
                    selected_logical_table = table["logical_name"]
                    selected_physical_table = table["physical_name"]
                    value_col = candidate_value_col
                    date_col = next((col for col in columns if "date" in col.lower()), None)
                    break

            if not selected_logical_table or not selected_physical_table or not value_col:
                return {"error": "No sales amount column found. Expected Amount, sales, revenue, total, or qty."}

            selected_cols = [quote_identifier(value_col)]
            if date_col:
                selected_cols.insert(0, quote_identifier(date_col))

            df = pd.read_sql_query(
                f"SELECT {', '.join(selected_cols)} FROM {quote_identifier(selected_physical_table)}",
                conn,
            )
        finally:
            conn.close()

        df[value_col] = pd.to_numeric(df[value_col], errors="coerce")

        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], format="%m-%d-%y", errors="coerce")
            if df[date_col].notna().sum() == 0:
                df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            history = (
                df.dropna(subset=[date_col, value_col])
                .groupby(date_col, as_index=False)[value_col]
                .sum()
                .sort_values(date_col)
            )
            labels = [date.strftime("%Y-%m-%d") for date in history[date_col]]
        else:
            history = df.dropna(subset=[value_col]).reset_index(drop=True)
            labels = [str(i + 1) for i in range(len(history))]

        values = history[value_col].tolist()
        if len(values) < 2:
            return {"error": f"Need at least 2 numeric {value_col} values to forecast."}

        predictions = forecast_values(values, periods=periods)

        if date_col:
            last_date = history[date_col].iloc[-1]
            future_labels = [
                (last_date + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(1, periods + 1)
            ]
        else:
            future_labels = [f"Forecast {i}" for i in range(1, periods + 1)]

        return {
            "date_column": date_col,
            "table": selected_logical_table,
            "value_column": value_col,
            "history": [
                {"period": label, "actual": float(value)}
                for label, value in zip(labels, values)
            ],
            "forecast": [
                {"period": label, "forecast": float(value)}
                for label, value in zip(future_labels, predictions)
            ],
        }

    except Exception as e:
        return {"error": str(e)}


@app.post("/upload")
async def upload_file(
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
):
    try:
        user_id = get_user_id(user)
        conn = get_db_connection()
        uploaded_tables = []

        try:
            cursor = conn.cursor()
            for file in files:
                contents = await file.read()
                df = read_upload_dataframe(file, contents)
                table_name = table_name_from_filename(file.filename)
                physical_name = physical_table_name(user_id, table_name)
                df.to_sql(physical_name, conn, if_exists="replace", index=False)
                cursor.execute(
                    """
                    INSERT INTO app_user_tables (
                        user_id,
                        logical_name,
                        physical_name,
                        source_file
                    )
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, logical_name)
                    DO UPDATE SET
                        physical_name = excluded.physical_name,
                        source_file = excluded.source_file
                    """,
                    (user_id, table_name, physical_name, file.filename),
                )
                uploaded_tables.append(
                    {
                        "file": file.filename,
                        "table": table_name,
                        "columns": list(df.columns),
                        "rows": len(df),
                    }
                )
            conn.commit()
        finally:
            conn.close()

        return {
            "message": f"{len(uploaded_tables)} file(s) uploaded successfully",
            "tables": uploaded_tables,
        }

    except Exception as e:
        return {"error": str(e)}
