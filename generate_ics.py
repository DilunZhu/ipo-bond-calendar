#!/usr/bin/env python3
"""
新股新债打新日历 ICS 生成器
数据来源：东方财富网
- 可转债：datacenter-web API (RPT_BOND_CB_LIST)
- 新股：datacenter-web API (RPTA_APP_IPOAPPLY)
生成符合 RFC 5545 标准的 .ics 文件，可被 Apple Calendar / Google Calendar / Outlook 等订阅
"""

import requests
import re
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# 数据获取
# ============================================================

def parse_jsonp_or_json(text):
    """解析 JSONP 或纯 JSON 响应"""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"jQuery\d+_\d+\((.*)\)", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 最后兜底尝试直接解析
    return json.loads(text)


def fetch_bonds(page_size=100):
    """获取可转债打新数据"""
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "PUBLIC_START_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": str(page_size),
        "pageNumber": "1",
        "reportName": "RPT_BOND_CB_LIST",
        "columns": "ALL",
        "quoteType": "0",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = parse_jsonp_or_json(resp.text)
        if "result" in data and data["result"] is not None and "data" in data["result"]:
            return data["result"]["data"]
    except Exception as e:
        print(f"[WARN] 获取可转债数据失败: {e}")
    return []


def fetch_stocks_from_ipoapply():
    """从东方财富 datacenter-web 获取新股申购数据（2026年新版 API）

    接口: RPTA_APP_IPOAPPLY（替代已废弃的 RPT_NEW_STOCK_INFO）
    关键字段:
    - SECURITY_CODE: 股票代码
    - SECURITY_NAME_ABBR: 股票简称
    - APPLY_CODE: 申购代码
    - APPLY_DATE: 申购日期
    - ISSUE_PRICE: 发行价格
    - AFTER_ISSUE_PE: 发行市盈率
    - INDUSTRY_PE_NEW / INDUSTRY_PE: 行业市盈率
    - ONLINE_APPLY_UPPER: 网上申购上限(股)
    - TOP_APPLY_MARKETCAP: 顶格申购需配市值(万元)
    - MARKET: 市场类型(如 深交所创业板)
    - BALLOT_NUM_DATE: 中签号公布日
    - BALLOT_PAY_DATE: 中签缴款日
    - LISTING_DATE: 上市日期
    """
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "APPLY_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "200",
        "pageNumber": "1",
        "reportName": "RPTA_APP_IPOAPPLY",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = parse_jsonp_or_json(resp.text)
        if data.get("success") and data.get("result") and data["result"].get("data"):
            return data["result"]["data"]
        else:
            print(f"[WARN] RPTA_APP_IPOAPPLY 返回异常: {data.get('message', 'unknown')}")
    except Exception as e:
        print(f"[WARN] RPTA_APP_IPOAPPLY 获取失败: {e}")
    return []


def fetch_stocks_from_legacy():
    """尝试旧接口 RPT_NEW_STOCK_INFO（已废弃，作为兜底）"""
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "APPLY_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "100",
        "pageNumber": "1",
        "reportName": "RPT_NEW_STOCK_INFO",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = parse_jsonp_or_json(resp.text)
        if "result" in data and data["result"] is not None and "data" in data["result"]:
            return data["result"]["data"]
    except Exception:
        pass
    return []


def fetch_stocks():
    """获取新股申购数据，优先使用新接口"""
    # 新接口 RPTA_APP_IPOAPPLY
    stocks = fetch_stocks_from_ipoapply()
    if stocks:
        print(f"[INFO] RPTA_APP_IPOAPPLY 可用，获取到 {len(stocks)} 条")
        return stocks, "ipoapply"

    # 兜底：旧接口
    print("[INFO] RPTA_APP_IPOAPPLY 不可用，尝试旧接口")
    stocks = fetch_stocks_from_legacy()
    if stocks:
        print(f"[INFO] 旧接口可用，获取到 {len(stocks)} 条")
        return stocks, "legacy"

    print("[WARN] 所有新股 API 均不可用，仅生成可转债日历")
    return [], "none"


# ============================================================
# ICS 生成
# ============================================================

def escape_ics(text):
    """转义 ICS 文本中的特殊字符"""
    if not text:
        return ""
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def format_date_ics(dt_str):
    """将 '2026-06-22 00:00:00' 或 '2026-06-22' 转为 ICS 日期格式 20260622"""
    if not dt_str:
        return None
    dt_str = str(dt_str).strip()
    # 取前10位即可
    return dt_str[:10].replace("-", "")


def make_uid(prefix, code, date_str):
    """生成稳定的 UID（同一事件多次生成 UID 一致）"""
    raw = f"{prefix}-{code}-{date_str}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, raw))


def build_bond_event(bond):
    """为单只可转债生成 VEVENT 块"""
    name = bond.get("SECURITY_NAME_ABBR", "未知转债")
    code = bond.get("SECURITY_CODE", "")
    date_raw = bond.get("PUBLIC_START_DATE", "")

    dt_start = format_date_ics(date_raw)
    if not dt_start:
        return None

    # 过滤掉历史数据（只保留今天及以后的）
    today = datetime.now().strftime("%Y%m%d")
    if dt_start < today:
        return None

    # 计算结束日期（次日）
    start_date = datetime.strptime(dt_start, "%Y%m%d")
    end_date = (start_date + timedelta(days=1)).strftime("%Y%m%d")

    uid = make_uid("bond", code, dt_start)
    summary = f"新债丨{name}"
    description = f"{code}丨9:15-15:00"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@ipo-bond-calendar",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{dt_start}",
        f"DTEND;VALUE=DATE:{end_date}",
        f"SUMMARY:{escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(description)}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "TRIGGER:-PT9H",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape_ics(summary)}",
        "END:VALARM",
        "END:VEVENT",
    ]

    return "\r\n".join(lines)


def build_stock_event(stock, source="ipoapply"):
    """为单只新股生成 VEVENT 块

    RPTA_APP_IPOAPPLY 字段映射:
    - SECURITY_CODE → 代码
    - SECURITY_NAME_ABBR → 简称
    - APPLY_DATE → 申购日期
    - MARKET → 市场类型
    """
    name = stock.get("SECURITY_NAME_ABBR", stock.get("SECURITY_NAME", "未知新股"))
    code = stock.get("SECURITY_CODE", "")
    date_raw = stock.get("APPLY_DATE", "")
    market = stock.get("MARKET", "") or stock.get("TRADE_MARKET", "") or ""

    dt_start = format_date_ics(date_raw)
    if not dt_start:
        return None

    today = datetime.now().strftime("%Y%m%d")
    if dt_start < today:
        return None

    # 计算结束日期（次日）
    start_date = datetime.strptime(dt_start, "%Y%m%d")
    end_date = (start_date + timedelta(days=1)).strftime("%Y%m%d")

    # 申购时间
    if "沪" in market or "上海" in market:
        apply_time = "9:30-11:30/13:00-15:00"
    elif "深" in market or "深圳" in market:
        apply_time = "9:15-11:30/13:00-15:00"
    elif "北" in market or "北京" in market:
        apply_time = "9:15-11:30/13:00-15:00"
    else:
        apply_time = "9:15-15:00"

    uid = make_uid("stock", code, dt_start)
    summary = f"新股丨{name}"
    description = f"{market}丨{code}丨{apply_time}"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@ipo-bond-calendar",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{dt_start}",
        f"DTEND;VALUE=DATE:{end_date}",
        f"SUMMARY:{escape_ics(summary)}",
        f"DESCRIPTION:{escape_ics(description)}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "TRIGGER:-PT9H",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{escape_ics(summary)}",
        "END:VALARM",
        "END:VEVENT",
    ]

    return "\r\n".join(lines)


def generate_ics(output_path="docs/ipo_bond_calendar.ics"):
    """主函数：获取数据并生成 ICS 文件"""
    print("[INFO] 正在获取可转债数据...")
    bonds = fetch_bonds()
    print(f"[INFO] 获取到 {len(bonds)} 条可转债数据")

    print("[INFO] 正在获取新股数据...")
    stocks, source = fetch_stocks()
    print(f"[INFO] 获取到 {len(stocks)} 条新股数据 (来源: {source})")

    # 生成事件
    events = []
    for bond in bonds:
        event = build_bond_event(bond)
        if event:
            events.append(event)

    for stock in stocks:
        event = build_stock_event(stock, source)
        if event:
            events.append(event)

    print(f"[INFO] 共生成 {len(events)} 条日历事件")

    # 组装 ICS
    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IPO-Bond-Calendar//CN//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:A股打新日历",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "X-WR-CALDESC:新股新债申购日历，每日自动更新",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:P1D",
    ]

    for event in events:
        ics_lines.append(event)

    ics_lines.append("END:VCALENDAR")

    ics_content = "\r\n".join(ics_lines)

    # 写入文件
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ics_content, encoding="utf-8")
    print(f"[OK] ICS 文件已生成: {out.absolute()}")
    print(f"[OK] 文件大小: {out.stat().st_size} bytes")

    return ics_content


if __name__ == "__main__":
    generate_ics()
