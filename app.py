import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
import requests

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="모의투자 대시보드",
    page_icon="📈",
    layout="wide",
)

DATA_FILE = "portfolio.json"

# ── 데이터 저장/로드 ─────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cash": 10_000_000, "holdings": {}, "history": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_data()

portfolio = st.session_state.portfolio

# ── 유틸 함수 ────────────────────────────────────────────────
def get_ticker(symbol: str) -> str:
    """한국 주식이면 .KS 붙이기"""
    symbol = symbol.upper().strip()
    if symbol.isdigit():
        return symbol + ".KS"
    return symbol

def fetch_price(symbol: str):
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    try:
        price = info.last_price
        currency = info.currency
        return price, currency
    except Exception:
        return None, None

def fetch_history(symbol: str, period: str = "6mo"):
    ticker = yf.Ticker(symbol)
    return ticker.history(period=period)

def get_display_name(symbol: str) -> str:
    try:
        info = yf.Ticker(symbol).info
        return info.get("longName") or info.get("shortName") or symbol
    except Exception:
        return symbol

# ── 사이드바: 잔고 요약 ───────────────────────────────────────
with st.sidebar:
    st.title("💼 내 포트폴리오")
    st.metric("보유 현금", f"₩{portfolio['cash']:,.0f}" if portfolio['cash'] > 0 else f"${abs(portfolio['cash']):,.0f}")

    if st.button("🔄 초기화 (1천만원)"):
        st.session_state.portfolio = {"cash": 10_000_000, "holdings": {}, "history": []}
        save_data(st.session_state.portfolio)
        st.rerun()

    st.divider()
    st.caption("보유 종목")
    if portfolio["holdings"]:
        for sym, h in portfolio["holdings"].items():
            st.write(f"**{sym}** — {h['qty']}주 @ {h['avg_price']:,.0f}")
    else:
        st.caption("없음")

# ── 탭 구성 ──────────────────────────────────────────────────
tab_mkt, tab0, tab1, tab2, tab3, tab4 = st.tabs(["📈 시장 현황", "🧭 투자 가이드", "🔍 종목 검색", "💸 매수/매도", "📊 포트폴리오", "📋 거래 내역"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB_MKT — 시장 현황
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_data(ttl=300)
def fetch_fear_and_greed():
    urls = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://fear-and-greed-index.p.rapidapi.com/v1/fgi",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
    }
    try:
        r = requests.get(urls[0], headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        score = round(float(data["fear_and_greed"]["score"]), 1)
        rating = data["fear_and_greed"]["rating"]
        return score, rating
    except Exception as e:
        return None, None

@st.cache_data(ttl=600)
def fetch_treasury_yields():
    try:
        from datetime import date
        ym = date.today().strftime("%Y%m")
        url = (
            f"https://home.treasury.gov/resource-center/data-chart-center/"
            f"interest-rates/daily-treasury-rates.csv/all/{ym}"
            f"?type=daily_treasury_yield_curve&field_tdr_date_value_month={ym}&page&_format=csv"
        )
        df = pd.read_csv(url)
        if df.empty:
            return None
        latest = df.iloc[0]
        return {
            "3yr": latest.get("3 Yr", None),
            "10yr": latest.get("10 Yr", None),
            "30yr": latest.get("30 Yr", None),
        }
    except Exception:
        return None

@st.cache_data(ttl=300)
def fetch_market_indicators():
    tickers = {
        "코스피":       "^KS11",
        "코스닥":       "^KQ11",
        "다우존스":     "^DJI",
        "나스닥":       "^IXIC",
        "S&P500":      "^GSPC",
        "USD/KRW":     "KRW=X",
        "금 (Gold)":   "GC=F",
        "WTI 원유":    "CL=F",
        "삼성전자":    "005930.KS",
    }
    rows = []
    for name, sym in tickers.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if len(hist) < 2:
                raise ValueError("no data")
            cur_val  = hist["Close"].iloc[-1]
            prev_val = hist["Close"].iloc[-2]
            chg      = cur_val - prev_val
            chg_pct  = chg / prev_val * 100
            # 단위 포맷
            if name == "USD/KRW":
                fmt = f"₩{cur_val:,.2f}"
                chg_fmt = f"{chg:+.2f}"
            elif name in ("코스피", "코스닥", "다우존스", "나스닥", "S&P500"):
                fmt = f"{cur_val:,.2f}"
                chg_fmt = f"{chg:+.2f}"
            elif name == "삼성전자":
                fmt = f"₩{cur_val:,.0f}"
                chg_fmt = f"₩{chg:+,.0f}"
            else:
                fmt = f"${cur_val:,.2f}"
                chg_fmt = f"${chg:+.2f}"
            rows.append({
                "지표": name,
                "현재가 (종가)": fmt,
                "전일 대비": chg_fmt,
                "등락률": chg_pct,
                "_up": chg >= 0,
            })
        except Exception:
            rows.append({"지표": name, "현재가 (종가)": "조회 실패", "전일 대비": "-", "등락률": 0.0, "_up": True})
    return rows

# ── 주간 스냅샷 저장/로드 ─────────────────────────────────────
HISTORY_FILE = "market_history.json"

INDICATOR_ORDER = [
    "코스피", "코스닥", "다우존스", "나스닥", "S&P500",
    "USD/KRW", "금 (Gold)", "WTI 원유", "삼성전자",
    "Fear & Greed Index", "미국채 3년", "미국채 10년", "미국채 30년",
]

def load_market_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            os.remove(HISTORY_FILE)  # 손상된 파일 제거
    return {}

def _json_safe(obj):
    """numpy/pandas bool·float → Python 기본형 변환"""
    if isinstance(obj, (bool,)):
        return bool(obj)
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    return obj

def save_market_snapshot(date_str: str, snapshot: dict):
    hist = load_market_history()
    # 모든 값을 JSON 직렬화 가능한 타입으로 변환
    safe_snap = {}
    for k, v in snapshot.items():
        safe_snap[k] = {
            "display": str(v["display"]),
            "raw": float(v["raw"]) if v["raw"] is not None else None,
            "up": bool(v["up"]),
        }
    hist[date_str] = safe_snap
    sorted_keys = sorted(hist.keys())
    if len(sorted_keys) > 14:
        for old_key in sorted_keys[:-14]:
            del hist[old_key]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

def build_snapshot(mkt_rows, fg_score, fg_rating, treasury):
    snap = {}
    for r in mkt_rows:
        snap[r["지표"]] = {
            "display": r["현재가 (종가)"],
            "raw": float(r["등락률"]),
            "up": bool(r["_up"]),
        }
    fg_label_map_local = {
        "Extreme Fear": "극도의 공포", "Fear": "공포",
        "Neutral": "중립", "Greed": "탐욕", "Extreme Greed": "극도의 탐욕"
    }
    if fg_score is not None:
        snap["Fear & Greed Index"] = {
            "display": f"{fg_score} ({fg_label_map_local.get(fg_rating, fg_rating)})",
            "raw": float(fg_score),
            "up": bool(fg_score >= 50),
        }
    bond_labels = [("미국채 3년", "3yr"), ("미국채 10년", "10yr"), ("미국채 30년", "30yr")]
    for label, key in bond_labels:
        if treasury and treasury.get(key) is not None:
            val = float(treasury[key])
            snap[label] = {"display": f"{val:.2f}%", "raw": val, "up": True}
        else:
            snap[label] = {"display": "조회 실패", "raw": None, "up": True}
    return snap

fg_label_map = {
    "Extreme Fear": "극도의 공포", "Fear": "공포",
    "Neutral": "중립", "Greed": "탐욕", "Extreme Greed": "극도의 탐욕"
}

with tab_mkt:
    st.header("📈 시장 현황")
    st.caption(f"종가 기준 · {datetime.now().strftime('%Y-%m-%d %H:%M')} 업데이트")

    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 6])
    with col_btn1:
        do_refresh = st.button("🔄 새로고침", key="mkt_refresh")
    with col_btn2:
        do_save = st.button("💾 오늘 저장", key="mkt_save")

    if do_refresh:
        st.cache_data.clear()
        st.rerun()

    with st.spinner("시장 데이터 불러오는 중..."):
        mkt_rows = fetch_market_indicators()
        fg_score, fg_rating = fetch_fear_and_greed()
        treasury = fetch_treasury_yields()

    # ── 오늘 스냅샷 자동 저장 (하루 1회) ──
    today_str = datetime.now().strftime("%Y-%m-%d")
    hist_data = load_market_history()
    current_snap = build_snapshot(mkt_rows, fg_score, fg_rating, treasury)

    if today_str not in hist_data or do_save:
        save_market_snapshot(today_str, current_snap)
        hist_data = load_market_history()

    # ── 뷰 전환 ──
    view = st.radio("보기 모드", ["오늘 현황", "주간 비교"], horizontal=True, label_visibility="collapsed")

    st.divider()

    # ════════════════════════════════════════
    # 뷰 1: 오늘 현황 테이블
    # ════════════════════════════════════════
    if view == "오늘 현황":
        # mkt_rows에서 yfinance 기반 전일 대비 값 인덱싱
        mkt_map = {r["지표"]: r for r in mkt_rows}

        rows_today = []
        for name in INDICATOR_ORDER:
            if name in current_snap:
                s = current_snap[name]
                # yfinance로 계산된 전일 대비 우선 사용
                chg_str = "-"
                chg_up = s["up"]
                if name in mkt_map and mkt_map[name]["전일 대비"] != "-":
                    raw_chg = mkt_map[name]["전일 대비"]
                    chg_pct = mkt_map[name]["등락률"]
                    arrow = "▲" if chg_pct >= 0 else "▼"
                    chg_str = f"{arrow} {raw_chg} ({abs(chg_pct):.2f}%)"
                    chg_up = chg_pct >= 0
                else:
                    # 채권 등 mkt_rows에 없는 항목은 히스토리 fallback
                    past_dates = sorted([d for d in hist_data.keys() if d < today_str], reverse=True)
                    yesterday_snap = hist_data.get(past_dates[0]) if past_dates else {}
                    if yesterday_snap and name in yesterday_snap:
                        try:
                            today_raw_str = s["display"].replace("₩","").replace("$","").replace(",","").replace("%","").split("(")[0].strip()
                            yest_raw_str  = yesterday_snap[name]["display"].replace("₩","").replace("$","").replace(",","").replace("%","").split("(")[0].strip()
                            today_val = float(today_raw_str)
                            yest_val  = float(yest_raw_str)
                            if yest_val != 0:
                                chg_pct = (today_val - yest_val) / yest_val * 100
                                arrow = "▲" if chg_pct >= 0 else "▼"
                                chg_str = f"{arrow} {abs(chg_pct):.2f}%"
                                chg_up = chg_pct >= 0
                        except Exception:
                            chg_str = "-"

                rows_today.append({
                    "지표": name,
                    "현재가 (종가)": s["display"],
                    "전일 대비": chg_str,
                    "_up": s["up"],
                    "_chg_up": chg_up,
                })

        df_today = pd.DataFrame(rows_today)
        df_show = df_today[["지표", "현재가 (종가)", "전일 대비"]].copy()

        def color_today(df):
            styles = []
            for i, row in df.iterrows():
                up = df_today.loc[i, "_up"]
                if "조회 실패" in str(row["현재가 (종가)"]):
                    styles.append(["background-color:#fff3cd"] * 3)
                else:
                    c = "#fdecea" if up else "#e3f2fd"
                    chg_up = df_today.loc[i, "_chg_up"]
                    chg_c = "#fdecea" if chg_up else "#e3f2fd"
                    styles.append([f"background-color:{c}", f"background-color:{c}", f"background-color:{chg_c}"])
            return pd.DataFrame(styles, columns=df.columns, index=df.index)

        def color_chg_text(val):
            if "▲" in str(val):
                return "color:#c0392b; font-weight:bold"
            elif "▼" in str(val):
                return "color:#1565c0; font-weight:bold"
            return ""

        styled_today = df_show.style.apply(
            lambda _: color_today(df_show), axis=None
        ).map(color_chg_text, subset=["전일 대비"]
        ).set_properties(**{"font-weight": "bold"}, subset=["지표"])

        st.dataframe(styled_today, use_container_width=True, hide_index=True, height=520)

        # Fear & Greed 게이지
        if fg_score is not None:
            st.subheader("😱 Fear & Greed Index")
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=fg_score,
                title={"text": fg_label_map.get(fg_rating, fg_rating), "font": {"size": 18}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "black", "thickness": 0.15},
                    "steps": [
                        {"range": [0, 25],   "color": "#d32f2f"},
                        {"range": [25, 45],  "color": "#f57c00"},
                        {"range": [45, 55],  "color": "#fbc02d"},
                        {"range": [55, 75],  "color": "#388e3c"},
                        {"range": [75, 100], "color": "#1b5e20"},
                    ],
                },
                number={"suffix": " / 100"},
            ))
            fig_gauge.update_layout(height=260, margin=dict(l=20, r=20, t=40, b=20))
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.plotly_chart(fig_gauge, use_container_width=True)

    # ════════════════════════════════════════
    # 뷰 2: 주간 비교 테이블
    # ════════════════════════════════════════
    else:
        sorted_dates = sorted(hist_data.keys())[-7:]  # 최근 7일
        n_days = len(sorted_dates)

        if n_days == 0:
            st.info("저장된 데이터가 없습니다. '💾 오늘 저장' 버튼을 눌러 첫 데이터를 기록하세요.")
        else:
            # 컬럼: 지표 | D1 | D2 | ... | D7
            col_headers = ["지표"] + sorted_dates
            table_rows = []

            for indicator in INDICATOR_ORDER:
                row = {"지표": indicator}
                for d in sorted_dates:
                    snap = hist_data.get(d, {})
                    entry = snap.get(indicator)
                    if entry:
                        row[d] = entry["display"]
                    else:
                        row[d] = "-"
                table_rows.append(row)

            df_week = pd.DataFrame(table_rows, columns=col_headers)

            # 셀 색상: 날짜 컬럼에 up/down 반영
            def color_week(df):
                n_rows, n_cols = df.shape
                styles = pd.DataFrame("", index=df.index, columns=df.columns)
                styles["지표"] = "font-weight:bold"
                for d in sorted_dates:
                    if d not in df.columns:
                        continue
                    for i, indicator in enumerate(INDICATOR_ORDER):
                        entry = hist_data.get(d, {}).get(indicator)
                        if entry and entry.get("display", "-") not in ("-", "조회 실패"):
                            bg = "#e8f5e9" if entry.get("up", True) else "#fdecea"
                        elif entry and entry.get("display") == "조회 실패":
                            bg = "#fff3cd"
                        else:
                            bg = ""
                        if i < len(df):
                            styles.at[i, d] = f"background-color:{bg}"
                return styles

            styled_week = df_week.style.apply(color_week, axis=None)

            # 날짜 헤더 짧게 표시 (MM/DD)
            rename_map = {d: d[5:] for d in sorted_dates}  # "2026-06-08" → "06/08"
            df_week_display = df_week.rename(columns=rename_map)
            styled_week = df_week_display.style.apply(
                lambda _: color_week(df_week).rename(columns=rename_map),
                axis=None
            )

            st.dataframe(styled_week, use_container_width=True, hide_index=True, height=520)

            # 지표별 추이 미니 차트
            st.subheader("📉 지표별 주간 추이")
            chart_options = [
                ind for ind in INDICATOR_ORDER
                if ind not in ("Fear & Greed Index", "미국채 3년", "미국채 10년", "미국채 30년")
            ]
            selected_indicator = st.selectbox("지표 선택", chart_options)

            trend_dates, trend_vals = [], []
            for d in sorted_dates:
                entry = hist_data.get(d, {}).get(selected_indicator)
                if entry and entry.get("raw") is not None:
                    try:
                        # 등락률이 아닌 실제 값을 표시하려면 display 파싱
                        raw_display = entry["display"]
                        num_str = raw_display.replace("₩", "").replace("$", "").replace(",", "").replace("%", "").split("(")[0].strip()
                        trend_vals.append(float(num_str))
                        trend_dates.append(d)
                    except Exception:
                        pass

            if len(trend_vals) >= 2:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=trend_dates, y=trend_vals,
                    mode="lines+markers+text",
                    text=[f"{v:,.2f}" for v in trend_vals],
                    textposition="top center",
                    line=dict(color="#1f77b4", width=2),
                    marker=dict(size=8),
                ))
                fig_trend.update_layout(
                    title=f"{selected_indicator} 주간 추이",
                    height=280,
                    margin=dict(l=0, r=0, t=40, b=0),
                    xaxis_title=None,
                    yaxis_title=None,
                )
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.caption("추이 차트를 보려면 최소 2일치 데이터가 필요합니다.")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 0 — 투자 가이드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab0:
    st.header("🧭 투자 가이드")
    st.caption("Motoo 모의투자 동호회 자료 기반 — 2026년 상반기 기준")

    # ── 섹션 1: 투자 철학 ──
    st.subheader("📌 핵심 투자 철학")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
**1. ETF·인덱스 중심 매매**
> 개별 종목 맞히기가 아니라 시장 흐름 이해가 목표.
> "무엇을 샀는가"보다 "왜 샀는가"가 더 중요.

**2. 레버리지는 확신 후 단계적 확대**
> 초기 레버리지 ≤ 20% → 상승 확인 → 점진적 확대.
> 하락 구간에서 레버리지 선진입 금지.

**3. 인버스는 헤지 수단 (단타 금지)**
> 상승장에서 인버스 단타 반복 = 수익률 잠식.
> 명확한 하락 전환 시에만 포지션 헤지 용도로 사용.
""")

    with col_b:
        st.markdown("""
**4. 수익 보존이 수익 확대보다 우선**
> 신고가 시장에서는 함부로 팔지 않는 것이 원칙.
> 장대 음봉(지수 3~4% 이상 급락) = 매도 시그널.

**5. 리스크 조절 = 비중 조절**
> 인버스가 아닌 포지션 크기를 줄여 리스크 관리.
> 잘못됐다고 느낄 때 손절 후 인덱스로 전환.

**6. 원칙의 기계적 준수**
> "원칙을 지키는 습관"이 수익의 핵심.
> 감정 기반 클릭 매수, 공포성 매도 경계.
""")

    st.divider()

    # ── 섹션 2: 매매 전략 패턴 ──
    st.subheader("🔄 매매 전략 패턴")

    steps = [
        ("1️⃣ 저점 확인", "지수 변동폭 축소 여부 확인\n→ 인덱스 ETF 분할 매수 시작", "#1f77b4"),
        ("2️⃣ 상승 확인", "20주선 이탈 없이 상승 지속\n→ 레버리지 비중 단계적 확대", "#2ca02c"),
        ("3️⃣ 수익 보존", "신고가 구간 진입\n→ 장대 음봉 대기, 매도 원칙 준수", "#ff7f0e"),
        ("4️⃣ 섹터 교체", "재료 소진 / 주도 섹터 변화 감지\n→ 다음 주도 ETF로 신속 환승", "#9467bd"),
    ]

    cols = st.columns(4)
    for col, (title, desc, color) in zip(cols, steps):
        col.markdown(
            f"""<div style="background:{color}22;border-left:4px solid {color};
            padding:12px;border-radius:6px;height:130px">
            <b style="font-size:1rem">{title}</b><br>
            <span style="font-size:0.85rem;white-space:pre-line">{desc}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown("")
    with st.expander("🚫 금지 매매 유형"):
        st.markdown("""
| 금지 유형 | 이유 |
|---|---|
| 개별 종목 2배 ETF (하락 중 매수) | 하락 구간에서 레버리지 = 손실 가속 |
| 인버스 ETF 단타 반복 | 상승장에서 수익률 지속 잠식 |
| 레버리지 + 인버스 동시 보유 | 수익률이 0%로 수렴 |
| VIX 2배 인버스 매수 | VIX는 단순 하락이 아닌 변동성 확대 시 상승 |
| 덜 오른 섹터 무작정 추격 | 기회비용 낭비, 주도 섹터 이탈 위험 |
""")

    st.divider()

    # ── 섹션 2-5: 멘토 명언 ──
    st.subheader("💬 멘토의 한마디")
    quotes = [
        ("오늘만큼 좋은 시장은 없다라고 생각될 때, 3일을 기다려라", "🕐"),
        ("3일이 계속 올라가도 3일 동안 리스크를 없앤다고 생각해야 한다", "📉"),
        ("쉬는 것도 투자다", "💤"),
    ]
    q_cols = st.columns(3)
    for col, (quote, icon) in zip(q_cols, quotes):
        col.markdown(
            f"""<div style="background:linear-gradient(135deg,#1f77b4,#2ca02c);
            padding:20px;border-radius:10px;text-align:center;height:120px;
            display:flex;flex-direction:column;justify-content:center">
            <div style="font-size:2rem">{icon}</div>
            <div style="color:white;font-size:0.95rem;font-weight:600;margin-top:8px;line-height:1.4">
            "{quote}"</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── 섹션 3: 향후 예상 투자 방향 ──
    st.subheader("🔭 향후 예상 투자 방향 (2026년 6월~)")

    outlook_data = [
        {
            "이슈": "🤖 AI 슈퍼사이클",
            "방향": "강세 지속",
            "색": "green",
            "내용": "AI 컴퓨팅 수요는 공급 대비 '슈퍼 리니어' 성장. 반도체·하이퍼스케일러 장기 강세 유지. Capex 연 70% 성장에도 수요 미달."
        },
        {
            "이슈": "🚀 스페이스X IPO",
            "방향": "변동성 주의",
            "색": "orange",
            "내용": "6월 전환 구간. IPO 전후 블랙홀 효과(유동성 흡수)로 기존 보유 종목 단기 조정 가능. 비중 축소 또는 관망 고려."
        },
        {
            "이슈": "🧠 Anthropic IPO",
            "방향": "긍정적",
            "색": "green",
            "내용": "2분기 흑자 전환 예고(BEP 달성). IPO 이후 재평가 기대. 구글·아마존 등 투자사 반사이익. 스페이스X 대비 밸류에이션 유리."
        },
        {
            "이슈": "🇰🇷 한국 순환매",
            "방향": "단계적 이동",
            "색": "blue",
            "내용": "삼성전자·하이닉스 → 삼성전기·LG이노텍(MLCC) → 바이오 순환 예상. 외국인 저가 매집 바이오 주시. ETF 레버리지 청산 도미노 경계."
        },
        {
            "이슈": "💾 마이크론(MU)",
            "방향": "상승 여력",
            "색": "green",
            "내용": "순이익 49위 → 9위 도약. 삼성전자 대비 PER 멀티플 확대 여력 큼. UBS 목표가 $1,600 제시. 단기 차익 실현 자금 주의."
        },
        {
            "이슈": "💱 달러/원 환율",
            "방향": "리스크 요인",
            "색": "orange",
            "내용": "1,500원 고착화 추세. 미국 비중 확대 시 환율 리스크 감안 필요. 전쟁발 달러 강세 + 원화 약세 구조 지속 가능성."
        },
    ]

    col1, col2 = st.columns(2)
    for i, item in enumerate(outlook_data):
        col = col1 if i % 2 == 0 else col2
        color_map = {"green": "#2ca02c", "orange": "#ff7f0e", "blue": "#1f77b4"}
        c = color_map[item["색"]]
        badge_color = {"green": "🟢", "orange": "🟡", "blue": "🔵"}
        col.markdown(
            f"""<div style="background:#f8f8f8;border:1px solid #ddd;border-left:5px solid {c};
            padding:14px;border-radius:6px;margin-bottom:10px">
            <b>{item['이슈']}</b>
            <span style="float:right;font-size:0.8rem;color:{c}">{badge_color[item['색']]} {item['방향']}</span><br>
            <span style="font-size:0.85rem;color:#444">{item['내용']}</span>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── 섹션 4: 관심 종목 빠른 조회 ──
    st.subheader("⭐ 관심 종목 현재가")
    watchlist = {
        "삼성전자": "005930.KS",
        "SK하이닉스": "000660.KS",
        "삼성전기": "009150.KS",
        "마이크론": "MU",
        "SOXL": "SOXL",
        "TQQQ": "TQQQ",
        "팔란티어": "PLTR",
        "구글": "GOOGL",
    }

    if st.button("🔄 시세 새로고침"):
        st.cache_data.clear()

    wl_cols = st.columns(4)
    for idx, (name, sym) in enumerate(watchlist.items()):
        col = wl_cols[idx % 4]
        try:
            price, cur = fetch_price(sym)
            if price:
                hist_1d = yf.Ticker(sym).history(period="5d")
                if len(hist_1d) >= 2:
                    chg = (hist_1d["Close"].iloc[-1] - hist_1d["Close"].iloc[-2]) / hist_1d["Close"].iloc[-2] * 100
                    cur_sym = "₩" if cur == "KRW" else "$"
                    col.metric(f"{name}", f"{cur_sym}{price:,.0f}", f"{chg:+.2f}%")
                else:
                    col.metric(name, f"{price:,.0f}")
        except Exception:
            col.metric(name, "조회 실패")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1 — 종목 검색
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_data(ttl=60)
def search_ticker(query: str):
    """종목명 또는 티커로 후보 목록 반환"""
    try:
        results = yf.Search(query, max_results=8).quotes
        candidates = []
        for r in results:
            sym = r.get("symbol", "")
            name = r.get("longname") or r.get("shortname") or sym
            exch = r.get("exchDisp", "")
            type_ = r.get("quoteType", "")
            if type_ in ("EQUITY", "ETF", "INDEX"):
                candidates.append({"symbol": sym, "name": name, "exchange": exch, "type": type_})
        return candidates
    except Exception:
        return []

with tab1:
    st.header("종목 검색 & 차트")
    col1, col2 = st.columns([2, 1])
    with col1:
        raw_input = st.text_input(
            "종목 코드 또는 종목명 입력",
            placeholder="예) 삼성전자 / 005930 / Apple / AAPL",
            help="한글 종목명, 영문 회사명, 또는 티커 코드로 검색 가능",
        )
    with col2:
        period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)

    # 선택된 티커를 세션에 유지
    if "selected_symbol" not in st.session_state:
        st.session_state.selected_symbol = None
    if raw_input != st.session_state.get("last_search_input", ""):
        st.session_state.selected_symbol = None
    st.session_state.last_search_input = raw_input

    if raw_input:
        # 티커 코드 직접 입력 여부 판단 (숫자 6자리 or 순수 영문 티커)
        is_direct = raw_input.strip().replace(".", "").isalnum() and not any(
            "가" <= c <= "힣" for c in raw_input
        )

        if is_direct:
            symbol = get_ticker(raw_input.strip().upper())
        else:
            # 종목명 검색 → 후보 선택
            with st.spinner("종목 검색 중..."):
                candidates = search_ticker(raw_input.strip())

            if not candidates:
                st.warning("검색 결과가 없습니다. 티커 코드로 직접 입력해보세요.")
                symbol = None
            elif st.session_state.selected_symbol is None:
                st.markdown("**검색 결과** — 아래에서 종목을 선택하세요")
                for i, c in enumerate(candidates):
                    label = f"{c['name']}  `{c['symbol']}`  ({c['exchange']})"
                    if st.button(label, key=f"cand_{i}"):
                        st.session_state.selected_symbol = c["symbol"]
                        st.rerun()
                symbol = None
            else:
                symbol = st.session_state.selected_symbol
                if st.button("🔄 다시 검색", key="reset_search"):
                    st.session_state.selected_symbol = None
                    st.rerun()
    else:
        symbol = None

    if symbol:
        with st.spinner(f"{symbol} 데이터 불러오는 중..."):
            price, currency = fetch_price(symbol)
            hist = fetch_history(symbol, period)

        if price is None or hist.empty:
            st.error("종목을 찾을 수 없습니다. 코드를 확인해주세요.")
        else:
            name = get_display_name(symbol)
            cur_sym = "₩" if currency == "KRW" else "$"

            c1, c2, c3 = st.columns(3)
            c1.metric("종목명", name)
            c2.metric("현재가", f"{cur_sym}{price:,.2f}")
            change = hist["Close"].iloc[-1] - hist["Close"].iloc[-2]
            change_pct = change / hist["Close"].iloc[-2] * 100
            c3.metric("전일 대비", f"{cur_sym}{change:,.2f}", f"{change_pct:+.2f}%")

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist["Open"],
                high=hist["High"],
                low=hist["Low"],
                close=hist["Close"],
                name=symbol,
            ))
            fig.update_layout(
                title=f"{name} ({symbol})",
                xaxis_rangeslider_visible=False,
                height=450,
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            vol_fig = px.bar(hist, x=hist.index, y="Volume", title="거래량", height=200)
            vol_fig.update_layout(margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
            st.plotly_chart(vol_fig, use_container_width=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2 — 매수 / 매도
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab2:
    st.header("매수 / 매도")

    col_b, col_s = st.columns(2)

    # ── 매수 ──
    with col_b:
        st.subheader("📗 매수")
        buy_raw = st.text_input("종목 코드", key="buy_sym", placeholder="005930 / AAPL")
        buy_qty = st.number_input("수량 (주)", min_value=1, value=1, key="buy_qty")

        if buy_raw:
            buy_sym = get_ticker(buy_raw)
            buy_price, buy_cur = fetch_price(buy_sym)
            if buy_price:
                total_buy = buy_price * buy_qty
                cur_sym = "₩" if buy_cur == "KRW" else "$"
                st.info(f"현재가: {cur_sym}{buy_price:,.2f} | 총 매수금액: {cur_sym}{total_buy:,.2f}")

                if st.button("✅ 매수 실행", type="primary"):
                    # KRW 환산 (USD라면 1400원 가정)
                    cost_krw = total_buy if buy_cur == "KRW" else total_buy * 1400
                    if portfolio["cash"] >= cost_krw:
                        portfolio["cash"] -= cost_krw
                        h = portfolio["holdings"].setdefault(buy_sym, {"qty": 0, "avg_price": 0})
                        prev_total = h["qty"] * h["avg_price"]
                        h["qty"] += buy_qty
                        h["avg_price"] = (prev_total + cost_krw) / h["qty"]
                        portfolio["history"].append({
                            "date": str(datetime.now().strftime("%Y-%m-%d %H:%M")),
                            "type": "매수",
                            "symbol": buy_sym,
                            "qty": buy_qty,
                            "price": buy_price,
                            "currency": buy_cur,
                            "total_krw": cost_krw,
                        })
                        save_data(portfolio)
                        st.success(f"{buy_sym} {buy_qty}주 매수 완료!")
                        st.rerun()
                    else:
                        st.error(f"잔고 부족! 필요: ₩{cost_krw:,.0f} / 보유: ₩{portfolio['cash']:,.0f}")
            else:
                st.warning("종목 코드를 확인해주세요.")

    # ── 매도 ──
    with col_s:
        st.subheader("📕 매도")
        holding_syms = list(portfolio["holdings"].keys())
        if not holding_syms:
            st.info("보유 중인 종목이 없습니다.")
        else:
            sell_sym = st.selectbox("종목 선택", holding_syms, key="sell_sym")
            max_qty = portfolio["holdings"][sell_sym]["qty"]
            sell_qty = st.number_input("수량 (주)", min_value=1, max_value=max_qty, value=1, key="sell_qty")

            sell_price, sell_cur = fetch_price(sell_sym)
            if sell_price:
                total_sell = sell_price * sell_qty
                cur_sym = "₩" if sell_cur == "KRW" else "$"
                avg = portfolio["holdings"][sell_sym]["avg_price"]
                gain_krw = (sell_price * (1 if sell_cur == "KRW" else 1400) - avg / max_qty * sell_qty)
                st.info(f"현재가: {cur_sym}{sell_price:,.2f} | 총 매도금액: {cur_sym}{total_sell:,.2f}")

                if st.button("✅ 매도 실행", type="primary"):
                    proceeds_krw = total_sell if sell_cur == "KRW" else total_sell * 1400
                    portfolio["cash"] += proceeds_krw
                    h = portfolio["holdings"][sell_sym]
                    h["qty"] -= sell_qty
                    if h["qty"] == 0:
                        del portfolio["holdings"][sell_sym]
                    portfolio["history"].append({
                        "date": str(datetime.now().strftime("%Y-%m-%d %H:%M")),
                        "type": "매도",
                        "symbol": sell_sym,
                        "qty": sell_qty,
                        "price": sell_price,
                        "currency": sell_cur,
                        "total_krw": proceeds_krw,
                    })
                    save_data(portfolio)
                    st.success(f"{sell_sym} {sell_qty}주 매도 완료!")
                    st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3 — 포트폴리오 현황
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab3:
    st.header("포트폴리오 현황")

    if not portfolio["holdings"]:
        st.info("보유 종목이 없습니다. 매수 탭에서 종목을 구매해보세요!")
    else:
        rows = []
        total_eval = 0
        total_cost = 0

        for sym, h in portfolio["holdings"].items():
            price, cur = fetch_price(sym)
            if price is None:
                continue
            eval_krw = price * h["qty"] * (1 if cur == "KRW" else 1400)
            cost_krw = h["avg_price"] * h["qty"]
            gain = eval_krw - cost_krw
            gain_pct = gain / cost_krw * 100 if cost_krw else 0
            total_eval += eval_krw
            total_cost += cost_krw
            cur_sym = "₩" if cur == "KRW" else "$"
            rows.append({
                "종목": sym,
                "수량": h["qty"],
                "평균단가(₩)": f"₩{h['avg_price']/h['qty']:,.0f}",
                "현재가": f"{cur_sym}{price:,.2f}",
                "평가금액(₩)": f"₩{eval_krw:,.0f}",
                "손익(₩)": f"₩{gain:+,.0f}",
                "수익률": f"{gain_pct:+.2f}%",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        total_assets = portfolio["cash"] + total_eval
        total_gain = total_eval - total_cost
        total_gain_pct = total_gain / total_cost * 100 if total_cost else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("보유 현금", f"₩{portfolio['cash']:,.0f}")
        c2.metric("주식 평가액", f"₩{total_eval:,.0f}")
        c3.metric("총 자산", f"₩{total_assets:,.0f}")
        c4.metric("총 손익", f"₩{total_gain:+,.0f}", f"{total_gain_pct:+.2f}%")

        # 파이 차트
        pie_data = {"현금": portfolio["cash"]}
        for r in rows:
            sym = r["종목"]
            val = float(r["평가금액(₩)"].replace("₩", "").replace(",", ""))
            pie_data[sym] = val

        fig_pie = px.pie(
            values=list(pie_data.values()),
            names=list(pie_data.keys()),
            title="자산 배분",
            hole=0.4,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4 — 거래 내역
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab4:
    st.header("거래 내역")
    if not portfolio["history"]:
        st.info("거래 내역이 없습니다.")
    else:
        hist_df = pd.DataFrame(portfolio["history"][::-1])
        hist_df = hist_df.rename(columns={
            "date": "일시", "type": "구분", "symbol": "종목",
            "qty": "수량", "price": "체결가", "currency": "통화", "total_krw": "원화금액"
        })
        hist_df["원화금액"] = hist_df["원화금액"].apply(lambda x: f"₩{x:,.0f}")
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
