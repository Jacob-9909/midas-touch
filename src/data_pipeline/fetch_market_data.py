"""Market Data Fetcher from open APIs (yfinance, FRED, ECOS).

This module manages fetching historical and real-time data for:
- Equities (Stock indices, specific equities)
- Fixed Income (Treasury yields, base rates)
- Exchange Rates (USD/KRW, EUR/KRW, etc.)
- Commodities (WTI, Brent, Gold, Silver)
And formats them to match Azure SQL `market_snapshots` table schema.
"""

import os
import logging
from datetime import datetime, timedelta
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API Keys Helpers
# ---------------------------------------------------------------------------
def _is_valid_key(key_name: str) -> bool:
    val = os.environ.get(key_name, "")
    if not val:
        return False
    if val.startswith("<") or val.endswith(">"):
        return False
    if "API-키" in val or "stlouisfed" in val:
        return False
    return True


FRED_API_KEY = os.environ.get("FRED_API_KEY") if _is_valid_key("FRED_API_KEY") else None
BOK_API_KEY = os.environ.get("BOK_API_KEY") if _is_valid_key("BOK_API_KEY") else None


# ---------------------------------------------------------------------------
# API Collectors
# ---------------------------------------------------------------------------
def fetch_yfinance_data(symbol: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch history from Yahoo Finance and return list of date-value dicts."""
    logger.info(f"Fetching from Yahoo Finance: {symbol} ({start_date} to {end_date})")
    try:
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if df.empty:
            logger.warning(f"No data returned for ticker {symbol} between {start_date} and {end_date}")
            return []
        
        # Flatten MultiIndex if it exists
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # yfinance columns might be a MultiIndex or simple Index depending on version and request
        # Let's extract the Close or Adj Close column safely.
        if "Adj Close" in df.columns:
            close_col = "Adj Close"
        elif "Close" in df.columns:
            close_col = "Close"
        else:
            # Fallback to the first column
            close_col = df.columns[0]
            
        results = []
        for dt, row in df.iterrows():
            # dt is Timestamp
            date_str = dt.strftime("%Y-%m-%d")
            
            # Handle possible MultiIndex or series values
            val = row[close_col]
            if isinstance(val, (pd.Series, list)):
                val = val[0]
            
            try:
                val = float(val)
                # Filter out NaN
                if pd.isna(val):
                    continue
                results.append({"date": date_str, "value": val})
            except (ValueError, TypeError):
                continue
        return results
    except Exception as e:
        logger.error(f"Error fetching {symbol} from Yahoo Finance: {e}")
        return []


def fetch_fred_data(series_id: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch history from FRED API."""
    if not FRED_API_KEY:
        logger.info(f"FRED API key not set or invalid. Skipping FRED for series: {series_id}")
        return []
    
    logger.info(f"Fetching from FRED: {series_id} ({start_date} to {end_date})")
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
        "observation_end": end_date
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for obs in data.get("observations", []):
            date_str = obs["date"]
            val_str = obs["value"]
            try:
                # FRED represents missing values as '.'
                if val_str == ".":
                    continue
                val = float(val_str)
                results.append({"date": date_str, "value": val})
            except (ValueError, TypeError):
                continue
        return results
    except Exception as e:
        logger.error(f"Error fetching from FRED series {series_id}: {e}")
        return []


def fetch_ecos_data(stat_code: str, cycle: str, item_code: str, start_date: str, end_date: str) -> list[dict]:
    """Fetch history from BOK ECOS API."""
    if not BOK_API_KEY:
        logger.info(f"BOK ECOS API key not set or invalid. Skipping ECOS for stat_code: {stat_code}")
        return []
    
    start_fmt = start_date.replace("-", "")
    end_fmt = end_date.replace("-", "")
    logger.info(f"Fetching from BOK ECOS: {stat_code}/{item_code} ({start_fmt} to {end_fmt})")
    
    # URL Format: http://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/1000/{stat_code}/{cycle}/{start}/{end}/{item_code}
    url = f"http://ecos.bok.or.kr/api/StatisticSearch/{BOK_API_KEY}/json/kr/1/1000/{stat_code}/{cycle}/{start_fmt}/{end_fmt}/{item_code}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        search_data = data.get("StatisticSearch", {})
        rows = search_data.get("row", [])
        if not rows:
            logger.warning(f"No rows returned from ECOS. Response: {data}")
            return []
            
        results = []
        for row in rows:
            time_str = row.get("TIME")
            if len(time_str) == 8:
                date_str = f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:]}"
            elif len(time_str) == 6:
                # Monthly data: YYYYMM -> YYYY-MM-01
                date_str = f"{time_str[:4]}-{time_str[4:6]}-01"
            else:
                date_str = time_str
                
            try:
                val = float(row.get("DATA_VALUE", 0))
                results.append({"date": date_str, "value": val})
            except (ValueError, TypeError):
                continue
        return results
    except Exception as e:
        logger.error(f"Error fetching from BOK ECOS: {e}")
        return []


# ---------------------------------------------------------------------------
# Unified Pipeline Class
# ---------------------------------------------------------------------------
class MarketDataPipeline:
    def __init__(self):
        # Configure targets with metadata
        # (data_type, sub_key, unit, source, yfinance_ticker, fred_id, ecos_args)
        # ecos_args format: (stat_code, cycle, item_code) or None
        self.targets = [
            # 1. Exchange Rates
            ("exchange_rate", "USD/KRW", "KRW", "BOK", "USDKRW=X", None, ("036Y001", "D", "0000001")),
            ("exchange_rate", "JPY/KRW", "KRW", "BOK", "JPYKRW=X", None, ("036Y001", "D", "0000002")),
            ("exchange_rate", "EUR/KRW", "KRW", "BOK", "EURKRW=X", None, ("036Y001", "D", "0000003")),
            
            # 2. Interest Rates & Bonds
            ("interest_rate", "US_10Y_BOND", "%", "FRED", "^TNX", "DGS10", None),
            ("interest_rate", "US_2Y_BOND", "%", "FRED", "^FVX", "DGS2", None), # Fallback to 5Y yield index ^FVX if needed
            ("interest_rate", "US_FED_RATE", "%", "FRED", "^IRX", "FEDFUNDS", None), # Fallback to 13W T-Bill index ^IRX
            ("interest_rate", "KR_BASE_RATE", "%", "BOK", None, None, ("722Y001", "D", "0101000")),
            ("interest_rate", "KR_CD_3M", "%", "BOK", None, None, ("022Y013", "D", "010500000")),
            
            # 3. Oil & Commodities
            ("oil_price", "WTI", "USD/BBL", "YahooFinance", "CL=F", None, None),
            ("oil_price", "BRENT", "USD/BBL", "YahooFinance", "BZ=F", None, None),
            ("gold_price", "GOLD_USD", "USD/oz", "YahooFinance", "GC=F", None, None),
            ("silver_price", "SILVER_USD", "USD/oz", "YahooFinance", "SI=F", None, None),
            
            # 4. Stock Market Indexes (Benchmark indices only, no individual stocks)
            ("stock", "S&P500", "pt", "YahooFinance", "^GSPC", None, None),
            ("stock", "KOSPI", "pt", "YahooFinance", "^KS11", None, None),
        ]

    def fetch_target(self, target: tuple, start_date: str, end_date: str) -> list[dict]:
        """Fetch a specific target asset with fallbacks."""
        data_type, sub_key, unit, primary_source, yf_ticker, fred_id, ecos_args = target
        
        logger.info(f"Processing target: {data_type}:{sub_key} (Primary: {primary_source})")
        results = []
        
        # Case A: ECOS (BOK)
        if primary_source == "BOK" and BOK_API_KEY and ecos_args:
            stat_code, cycle, item_code = ecos_args
            results = fetch_ecos_data(stat_code, cycle, item_code, start_date, end_date)
            if results:
                # ECOS data format conversion for output
                return [{"snapshot_date": r["date"], "data_type": data_type, "sub_key": sub_key, "value": r["value"], "unit": unit, "source": "BOK"} for r in results]
            logger.warning(f"BOK ECOS fetch failed or empty. Falling back to yfinance or default for {sub_key}")
            
        # Case B: FRED
        if primary_source == "FRED" and FRED_API_KEY and fred_id:
            results = fetch_fred_data(fred_id, start_date, end_date)
            if results:
                return [{"snapshot_date": r["date"], "data_type": data_type, "sub_key": sub_key, "value": r["value"], "unit": unit, "source": "FRED"} for r in results]
            logger.warning(f"FRED fetch failed or empty. Falling back to yfinance for {sub_key}")
            
        # Fallback / Direct yfinance
        if yf_ticker:
            results = fetch_yfinance_data(yf_ticker, start_date, end_date)
            if results:
                return [{"snapshot_date": r["date"], "data_type": data_type, "sub_key": sub_key, "value": r["value"], "unit": unit, "source": "YahooFinance"} for r in results]
        
        # If absolutely nothing works for Korean Interest Rates (e.g. KR_BASE_RATE without BOK key)
        if sub_key == "KR_BASE_RATE":
            logger.info("Using hardcoded fallback base rate of 3.50% for KR_BASE_RATE")
            # Generate daily records for target range
            date_range = pd.date_range(start=start_date, end=end_date)
            return [{"snapshot_date": d.strftime("%Y-%m-%d"), "data_type": data_type, "sub_key": sub_key, "value": 3.50, "unit": unit, "source": "HardcodedFallback"} for d in date_range]
            
        if sub_key == "KR_CD_3M":
            logger.info("Using hardcoded fallback base rate of 3.55% for KR_CD_3M")
            date_range = pd.date_range(start=start_date, end=end_date)
            return [{"snapshot_date": d.strftime("%Y-%m-%d"), "data_type": data_type, "sub_key": sub_key, "value": 3.55, "unit": unit, "source": "HardcodedFallback"} for d in date_range]

        logger.error(f"Failed to fetch any data for {data_type}:{sub_key}")
        return []

    def fetch_all(self, start_date: str, end_date: str) -> list[dict]:
        """Fetch all configured target market data."""
        all_snapshots = []
        for target in self.targets:
            snapshots = self.fetch_target(target, start_date, end_date)
            all_snapshots.extend(snapshots)
            logger.info(f"Loaded {len(snapshots)} snapshots for {target[1]}")
        return all_snapshots


def fetch_realtime_stock(symbol: str) -> dict:
    """Fetch real-time stock price and metadata from Yahoo Finance on-demand."""
    logger.info(f"On-demand real-time query for: {symbol}")
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        # Determine currency
        currency = info.get("currency")
        if not currency:
            currency = "KRW" if (symbol.endswith(".KS") or symbol.endswith(".KQ")) else "USD"
            
        # Get current price
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            try:
                price = ticker.fast_info.get("last_price")
            except Exception:
                price = None
            
        # Get previous close to calculate change
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if prev_close is None:
            try:
                prev_close = ticker.fast_info.get("previous_close")
            except Exception:
                prev_close = None
            
        change = 0.0
        change_pct = 0.0
        if price is not None and prev_close is not None and prev_close > 0:
            change = price - prev_close
            change_pct = (change / prev_close) * 100.0
            
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName") or symbol,
            "price": float(price) if price is not None else None,
            "change": float(change),
            "change_percent": float(change_pct),
            "currency": currency,
            "fetched_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching real-time stock {symbol}: {e}")
        return {
            "symbol": symbol,
            "name": symbol,
            "price": None,
            "change": 0.0,
            "change_percent": 0.0,
            "currency": "USD",
            "error": str(e),
            "fetched_at": datetime.now().isoformat()
        }

