import requests
import pandas as pd
import streamlit as st
from forecasting import forecast_values


st.set_page_config(page_title="QueryLens AI", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --primary: #0f766e;
        --secondary: #2563eb;
        --accent: #f59e0b;
        --ink: #111827;
        --soft: #f8fafc;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(15, 118, 110, 0.13), transparent 34rem),
            radial-gradient(circle at top right, rgba(245, 158, 11, 0.12), transparent 28rem),
            linear-gradient(180deg, #ffffff 0%, #f8fafc 46%, #eef6f5 100%);
        color: var(--ink);
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 2rem 2.25rem;
        margin: 0 0 1.5rem 0;
        border-radius: 8px;
        background:
            linear-gradient(135deg, rgba(15, 118, 110, 0.96), rgba(37, 99, 235, 0.92)),
            linear-gradient(90deg, #0f766e, #2563eb);
        color: white;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.16);
        animation: hero-enter 700ms ease-out both;
    }

    .hero::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,0.20) 45%, transparent 65%);
        transform: translateX(-120%);
        animation: shimmer 4.5s ease-in-out infinite;
    }

    .hero h1 {
        position: relative;
        z-index: 1;
        margin: 0;
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: 0;
    }

    .hero p {
        position: relative;
        z-index: 1;
        max-width: 760px;
        margin: 0.55rem 0 0 0;
        color: rgba(255,255,255,0.9);
        font-size: 1.05rem;
        line-height: 1.55;
    }

    .metric-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin: 0 0 1.35rem 0;
    }

    .metric-pill {
        padding: 0.9rem 1rem;
        border: 1px solid rgba(15, 118, 110, 0.16);
        border-radius: 8px;
        background: rgba(255,255,255,0.78);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        animation: fade-up 620ms ease-out both;
    }

    .metric-pill:nth-child(2) {
        animation-delay: 90ms;
    }

    .metric-pill:nth-child(3) {
        animation-delay: 180ms;
    }

    .metric-pill strong {
        display: block;
        color: var(--primary);
        font-size: 0.86rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .metric-pill span {
        display: block;
        margin-top: 0.25rem;
        color: #334155;
        font-size: 0.95rem;
    }

    div.stButton > button {
        border: 0;
        border-radius: 8px;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        color: white;
        font-weight: 700;
        transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
        box-shadow: 0 10px 22px rgba(37, 99, 235, 0.18);
    }

    div.stButton > button:hover {
        transform: translateY(-1px);
        filter: brightness(1.04);
        box-shadow: 0 14px 28px rgba(37, 99, 235, 0.24);
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stNumberInput"] input {
        border-radius: 8px;
        border-color: rgba(15, 118, 110, 0.28);
    }

    @keyframes hero-enter {
        from {
            opacity: 0;
            transform: translateY(12px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes shimmer {
        0%, 55% {
            transform: translateX(-120%);
        }
        100% {
            transform: translateX(120%);
        }
    }

    @keyframes fade-up {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @media (max-width: 760px) {
        .hero {
            padding: 1.45rem 1.25rem;
        }

        .hero h1 {
            font-size: 1.85rem;
        }

        .metric-strip {
            grid-template-columns: 1fr;
        }
    }
    </style>

    <section class="hero">
        <h1>QueryLens AI</h1>
        <p>Upload business data, ask plain-English questions, inspect generated SQL, and turn sales history into a quick forecast.</p>
    </section>

    <section class="metric-strip">
        <div class="metric-pill">
            <strong>Upload</strong>
            <span>CSV and Excel datasets</span>
        </div>
        <div class="metric-pill">
            <strong>Ask</strong>
            <span>Natural-language SQL questions</span>
        </div>
        <div class="metric-pill">
            <strong>Forecast</strong>
            <span>Future sales from Amount and Date</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

api_url = st.text_input("FastAPI URL", value="http://127.0.0.1:8000")


def api_is_online(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        return r.ok
    except Exception:
        return False


online = api_is_online(api_url)
if online:
    st.success(f"Backend connected: {api_url}")
else:
    st.error(
        f"Backend not reachable at {api_url}. Start FastAPI first: "
        "uvicorn main:app --port 8000"
    )


def render_sales_forecast(rows: list[dict], prompt: str, periods: int = 5) -> None:
    if not rows:
        return

    df = pd.DataFrame(rows)
    if df.empty:
        return

    preferred_value_cols = ["amount", "sales", "revenue", "total", "qty"]
    value_col = None
    numeric_values = None

    for preferred in preferred_value_cols:
        matching_cols = [col for col in df.columns if col.lower().strip() == preferred]
        for col in matching_cols:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(values) > 0:
                value_col = col
                numeric_values = values
                break
        if value_col:
            break

    if value_col is None:
        for col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(values) > 0:
                value_col = col
                numeric_values = values
                break

    if value_col is None or numeric_values is None:
        return

    date_cols = [col for col in df.columns if "date" in col.lower()]
    history = pd.DataFrame({"value": pd.to_numeric(df[value_col], errors="coerce")})

    if date_cols:
        date_col = date_cols[0]
        history["date"] = pd.to_datetime(df[date_col], format="%m-%d-%y", errors="coerce")
        if history["date"].notna().sum() == 0:
            history["date"] = pd.to_datetime(df[date_col], errors="coerce")
        history = history.dropna(subset=["date", "value"])
        history = history.groupby("date", as_index=False)["value"].sum().sort_values("date")
        labels = [date.strftime("%Y-%m-%d") for date in history["date"]]
    else:
        history = history.dropna(subset=["value"]).reset_index(drop=True)
        labels = [str(i + 1) for i in range(len(history))]

    if history.empty:
        return

    values = history["value"].tolist()
    if len(values) < 2:
        st.info(f"Need at least 2 numeric `{value_col}` values to forecast.")
        return

    predictions = forecast_values(values, periods=periods)

    if date_cols:
        last_date = history["date"].iloc[-1]
        future_labels = [
            (last_date + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(1, periods + 1)
        ]
    else:
        future_labels = [f"Forecast {i}" for i in range(1, periods + 1)]

    chart_df = pd.DataFrame(
        {
            "Actual": values + [None] * periods,
            "Forecast": [None] * (len(values) - 1) + [values[-1]] + predictions,
        },
        index=labels + future_labels,
    )

    should_auto_show = "forecast" in prompt.lower() or value_col.lower() in {"amount", "sales", "revenue"}
    if should_auto_show:
        st.subheader(f"Sales Forecast from `{value_col}`")
        st.line_chart(chart_df)
        st.dataframe(
            pd.DataFrame({"Period": future_labels, "Forecast": predictions}),
            use_container_width=True,
        )

st.subheader("1) Upload CSV/Excel")
uploaded_file = st.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])

if uploaded_file and st.button("Upload"):
    if not online:
        st.warning("Backend is offline. Start FastAPI and try again.")
        st.stop()
    try:
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
        }
        response = requests.post(f"{api_url}/upload", files=files, timeout=60)
        data = response.json()
        if response.ok:
            st.success(data.get("message", "Uploaded"))
            st.write(data)
        else:
            st.error(data)
    except Exception as exc:
        st.error(f"Upload failed: {exc}")

st.subheader("2) Ask in plain English")
prompt = st.text_area("Your question", placeholder="e.g. show top 5 cities by customer count")

if st.button("Run Query"):
    if not prompt.strip():
        st.warning("Enter a question first.")
    elif not online:
        st.warning("Backend is offline. Start FastAPI and try again.")
    else:
        try:
            response = requests.post(
                f"{api_url}/query",
                json={"user_query": prompt},
                timeout=90,
            )
            data = response.json()
            if response.ok:
                if "error" in data:
                    st.error(data["error"])
                    if data.get("sql"):
                        st.caption("Generated SQL")
                        st.code(data["sql"], language="sql")
                else:
                    st.caption("Generated SQL")
                    st.code(data.get("sql", ""), language="sql")
                    st.write(f"Rows returned: {data.get('row_count', 0)}")
                    rows = data.get("rows", [])
                    if isinstance(rows, list) and rows:
                        st.dataframe(rows, use_container_width=True)
                        render_sales_forecast(rows, prompt)
                    else:
                        st.info("Query ran successfully, but returned no rows.")
            else:
                st.error(data)
        except Exception as exc:
            st.error(f"Query failed: {exc}")

st.subheader("3) Sales Forecast")
forecast_periods = st.number_input("Forecast periods", min_value=1, max_value=30, value=5)

if st.button("Generate Sales Forecast"):
    if not online:
        st.warning("Backend is offline. Start FastAPI and try again.")
    else:
        try:
            response = requests.get(
                f"{api_url}/forecast/sales",
                params={"periods": int(forecast_periods)},
                timeout=60,
            )
            data = response.json()
            if "error" in data:
                st.error(data["error"])
            else:
                history = data.get("history", [])
                forecast = data.get("forecast", [])
                actual_values = [row["actual"] for row in history]
                predicted_values = [row["forecast"] for row in forecast]
                labels = [row["period"] for row in history] + [
                    row["period"] for row in forecast
                ]

                chart_df = pd.DataFrame(
                    {
                        "Actual": actual_values + [None] * len(predicted_values),
                        "Forecast": [None] * (len(actual_values) - 1)
                        + [actual_values[-1]]
                        + predicted_values,
                    },
                    index=labels,
                )
                st.caption(
                    f"Using `{data.get('value_column')}`"
                    + (
                        f" grouped by `{data.get('date_column')}`"
                        if data.get("date_column")
                        else ""
                    )
                )
                st.line_chart(chart_df)
                st.dataframe(pd.DataFrame(forecast), use_container_width=True)
        except Exception as exc:
            st.error(f"Forecast failed: {exc}")
