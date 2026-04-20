from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import sqlite3
import pandas as pd
from io import StringIO, BytesIO
from ai import generate_sql
from forecasting import forecast_values

app = FastAPI()


class Query(BaseModel):
    user_query: str


def get_schema():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            schema[table] = columns

        return schema
    finally:
        conn.close()


def run_query(query):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
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


@app.get("/")
def home():
    return {"message": "AI Data Pipeline Running"}


@app.get("/schema")
def schema():
    return {"schema": get_schema()}


@app.post("/query")
def query_db(query: Query):
    try:
        schema_map = get_schema()
        if not schema_map:
            return {"error": "No tables found. Upload a CSV/Excel file first."}

        sql = generate_sql(query.user_query, schema_map)
        result = run_query(sql)

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
def forecast_sales(periods: int = 5):
    try:
        if periods < 1:
            return {"error": "periods must be at least 1"}

        conn = sqlite3.connect("database.db")
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(uploaded_data)")
            columns = [row[1] for row in cursor.fetchall()]

            if not columns:
                return {"error": "No uploaded_data table found. Upload a CSV/Excel file first."}

            date_col = next((col for col in columns if "date" in col.lower()), None)
            value_col = next(
                (
                    col
                    for target in ["amount", "sales", "revenue", "total", "qty"]
                    for col in columns
                    if col.lower().strip() == target
                ),
                None,
            )

            if not value_col:
                return {"error": "No sales amount column found. Expected Amount, sales, revenue, total, or qty."}

            selected_cols = [quote_identifier(value_col)]
            if date_col:
                selected_cols.insert(0, quote_identifier(date_col))

            df = pd.read_sql_query(
                f"SELECT {', '.join(selected_cols)} FROM uploaded_data",
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
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if file.filename and file.filename.lower().endswith(".csv"):
            try:
                df = pd.read_csv(StringIO(contents.decode("utf-8")))
            except Exception:
                df = pd.read_csv(StringIO(contents.decode("latin-1")))
        else:
            df = pd.read_excel(BytesIO(contents))

        conn = sqlite3.connect("database.db")
        df.to_sql("uploaded_data", conn, if_exists="replace", index=False)
        conn.close()

        return {
            "message": "File uploaded successfully",
            "table": "uploaded_data",
            "columns": list(df.columns),
            "rows": len(df),
        }

    except Exception as e:
        return {"error": str(e)}
