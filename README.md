# finance-app

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Financial Modeling Prep API key before running the app. You can use either Streamlit secrets or an environment variable.

### Option 1: Streamlit secrets

Create `.streamlit/secrets.toml`:

```toml
FMP_API_KEY = "your_fmp_api_key"
```

### Option 2: Environment variable

```bash
export FMP_API_KEY="your_fmp_api_key"
```

Run the app:

```bash
streamlit run app.py
```

## API notes

- ISIN lookup uses OpenFIGI.
- ETF look-through data uses Financial Modeling Prep.
- If the FMP key is missing, invalid, or rate-limited, the app now shows an in-app warning instead of failing silently.
