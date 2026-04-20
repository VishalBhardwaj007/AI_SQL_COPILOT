from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from ai import generate_sql
from db import run_query
import pandas as pd
import sqlite3

fastapi_app = FastAPI()

class QueryRequest(BaseModel):
    user_query: str

def get_schema():
    conn = sqlite3.connect("ecommerce.db")
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schema = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            schema[table] = [row[1] for row in cursor.fetchall()]

        return schema
    finally:
        conn.close()

@fastapi_app.get("/")
def home():
    return {"message": "AI SQL Copilot Running ðŸš€"}

@fastapi_app.post("/query")
def query_db(request: QueryRequest):
    schema = get_schema()
    sql = generate_sql(request.user_query, schema)
    results, columns = run_query(sql)
    
    return {
        "input": request.user_query,
        "sql": sql,
        "result": results,
        "columns": columns
    }

@fastapi_app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if file.filename and file.filename.lower().endswith(".csv"):
            from io import StringIO
            try:
                df = pd.read_csv(StringIO(contents.decode("utf-8")))
            except UnicodeDecodeError:
                df = pd.read_csv(StringIO(contents.decode("latin-1")))
        else:
            from io import BytesIO
            df = pd.read_excel(BytesIO(contents))

        conn = sqlite3.connect("ecommerce.db")
        df.to_sql("uploaded_data", conn, if_exists="replace", index=False)
        conn.close()

        return {
            "message": "File uploaded successfully",
            "columns": list(df.columns),
            "rows": len(df)
        }
    except Exception as e:
        return {"error": str(e)}

# For uvicorn to find the app
app = fastapi_app
