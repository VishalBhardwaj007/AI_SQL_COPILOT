import pandas as pd
import requests
import streamlit as st
from forecast import forecast_sales   

API_BASE_URL = "http://127.0.0.1:8000"   

st.title("AI SQL Copilot")

# -------------------------------
# Upload Section
# -------------------------------
st.header("Upload Data File")

uploaded_file = st.file_uploader(
    "Choose a CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None and st.button("Upload File"):
    try:
        with st.spinner("Uploading..."):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file,
                    uploaded_file.type,
                )
            }

            response = requests.post(
                f"{API_BASE_URL}/upload",
                files=files,
                timeout=30,
            )

        data = response.json()

        if "error" in data:
            st.error(data["error"])
        else:
            st.success(data.get("message", "Uploaded"))
            st.write("Columns:", data.get("columns", []))
            st.write("Rows:", data.get("rows", 0))

    except Exception as e:
        st.error(f"Upload Error: {str(e)}")


# -------------------------------
# Query Section
# -------------------------------
st.header("Query Database")

suggestions = [
    "Show all customers",
    "Show customers from Delhi",
    "Show all from uploaded_data",
    "forecast sales",   
]

query = st.selectbox("Choose query:", suggestions)

if st.button("Run Query"):
    try:
        with st.spinner("Thinking..."):
            response = requests.post(
                f"{API_BASE_URL}/query",
                json={"user_query": query},
                timeout=30,
            )

        data = response.json()

        if "error" in data:
            st.error(data["error"])

        else:
            st.subheader("Generated SQL")
            st.code(data["sql"])

            if data["result"]:
                df = pd.DataFrame(data["result"], columns=data["columns"])
                st.subheader("Data")
                st.dataframe(df)

                # -------------------------------
                # STEP 3: Detect numeric columns
                # -------------------------------
                numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()

                # -------------------------------
                # STEP 4: Forecast Button
                # -------------------------------
                if st.button("📈 Forecast"):
                    if numeric_cols:
                        col = numeric_cols[0]

                        preds = forecast_sales(df, col)

                        st.subheader(f"Forecast for {col}")

                        full_data = list(df[col]) + list(preds)

                        st.line_chart(full_data)
                    else:
                        st.warning("No numeric column found")

                # -------------------------------
                # STEP 5: Auto Forecast (AI trigger)
                # -------------------------------
                if "forecast" in query.lower():
                    if numeric_cols:
                        col = numeric_cols[0]

                        preds = forecast_sales(df, col)

                        st.subheader("📈 Auto Forecast")

                        full_data = list(df[col]) + list(preds)

                        st.line_chart(full_data)

                # -------------------------------
                # Existing chart
                # -------------------------------
                if "city" in [col.lower() for col in data["columns"]]:
                    city_col = next(
                        col for col in data["columns"] if col.lower() == "city"
                    )
                    st.subheader("City Distribution")
                    st.bar_chart(df[city_col].value_counts())

            else:
                st.info("No data returned")

    except Exception as e:
        st.error(f"Error: {str(e)}")
