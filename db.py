import sqlite3

def get_connection():
    return sqlite3.connect("ecommerce.db")

def run_query(query):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(query)
    
    if query.strip().lower().startswith("select"):
        results = cursor.fetchall()
        column_names = [desc[0] for desc in cursor.description]
    else:
        conn.commit()
        results = []
        column_names = []
    
    conn.close()
    return results, column_names
