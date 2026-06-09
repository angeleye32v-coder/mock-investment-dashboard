import yfinance as yf
import json, os
from datetime import datetime, timedelta

base = r'D:\AI\mock-investment-dashboard'
HISTORY_FILE = os.path.join(base, 'market_history.json')

tickers = {
    '코스피':    '^KS11',
    '코스닥':    '^KQ11',
    '다우존스':  '^DJI',
    '나스닥':    '^IXIC',
    'S&P500':   '^GSPC',
    'USD/KRW':  'KRW=X',
    '금 (Gold)': 'GC=F',
    'WTI 원유':  'CL=F',
    '삼성전자':  '005930.KS',
}

# 최근 6일치 날짜
dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, 0, -1)]

# 종목별 10일치 데이터 수집
hist_data = {}
for name, sym in tickers.items():
    try:
        df = yf.Ticker(sym).history(period='10d')
        if df.index.tzinfo:
            df.index = df.index.tz_localize(None)
        hist_data[name] = df
        print(f'{name}: {len(df)}일치')
    except Exception as e:
        print(f'{name}: 실패 - {e}')

# 기존 히스토리 로드
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        market_hist = json.load(f)
else:
    market_hist = {}

# 날짜별 스냅샷 저장
for date_str in dates:
    if date_str in market_hist:
        print(f'{date_str}: 이미 존재, 스킵')
        continue
    snap = {}
    for name, sym in tickers.items():
        try:
            df = hist_data.get(name)
            if df is None or df.empty:
                continue
            day_data = df[df.index.strftime('%Y-%m-%d') == date_str]
            if day_data.empty:
                continue
            val = float(day_data['Close'].iloc[-1])
            if name == 'USD/KRW':
                display = f'₩{val:,.2f}'
            elif name in ('코스피', '코스닥', '다우존스', '나스닥', 'S&P500'):
                display = f'{val:,.2f}'
            elif name == '삼성전자':
                display = f'₩{val:,.0f}'
            else:
                display = f'${val:,.2f}'
            snap[name] = {'display': display, 'raw': val, 'up': True}
        except Exception as e:
            pass
    if snap:
        market_hist[date_str] = snap
        print(f'{date_str}: {len(snap)}개 지표 저장 완료')

with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
    json.dump(market_hist, f, ensure_ascii=False, indent=2)

print('\n완료! 저장된 날짜:', sorted(market_hist.keys()))
