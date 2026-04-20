# AI SQL Copilot

AI SQL Copilot is a Python-based data assistant that converts natural language questions into SQL queries, runs them on uploaded datasets, and displays results through a Streamlit interface.

## Features

- Upload CSV or Excel files and store them as a SQLite table.
- Generate SQLite `SELECT` queries from natural language prompts using the Groq LLM API.
- View generated SQL before inspecting query results.
- Display results in interactive tables and charts.
- Run basic sales/revenue forecasting using Pandas and NumPy.
- Expose backend APIs through FastAPI.

## Tech Stack

- Python
- FastAPI
- Streamlit
- SQLite
- Pandas
- NumPy
- Groq API

## Project Structure

```text
AI_SQL_COPILOT/
├── main.py              # FastAPI backend
├── ui.py                # Streamlit UI
├── ai.py                # Groq LLM SQL generation
├── forecasting.py       # Forecasting logic
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment variables
└── README.md
```

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file by copying `.env.example`, then add your Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

## Run the Application

Start the FastAPI backend:

```bash
uvicorn main:app --reload
```

In another terminal, start the Streamlit UI:

```bash
streamlit run ui.py
```

Open the Streamlit URL shown in the terminal, usually:

```text
http://localhost:8501
```

## Usage

1. Upload a CSV or Excel file.
2. Ask a natural language question about the data.
3. Review the generated SQL query.
4. View results in table/chart format.
5. Use forecasting when numeric sales or revenue data is available.

## Notes

- Do not commit `.env`, database files, virtual environments, or MySQL local data.
- Uploaded data is stored locally in `database.db`, which is ignored by Git.
