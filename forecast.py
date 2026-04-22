import pandas as pd
import numpy as np   
from sklearn.linear_model import LinearRegression

def forecast_sales(df, column):
    df = df.copy()

    df["index"] = range(len(df))

    X = df[["index"]]
    y = df[column]

    model = LinearRegression()
    model.fit(X, y)

    future_index = np.array(range(len(df), len(df) + 10)).reshape(-1, 1)

    predictions = model.predict(future_index)

    return predictions