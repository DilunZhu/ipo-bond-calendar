#!/usr/bin/env python3
"""
新股新债打新日历 ICS 生成器
数据来源：东方财富网
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
        
        # 尝试新格式：直接 JSON
        try:
            data = resp.json()
        except json.JSONDecodeError:
            # 尝试旧格式：jQuery 回调
            match = re.search(r"jQuery\d+_\d+\((.*)\)", resp.text)
            if match:
                json_text = match.group(1)
                data = json.loads(json_text)
            else:
                print(f"[DEBUG] 响应格式未识别，原文前500字：{resp.text[:500]}")
                return []
        
        if "result" in data and data["result"] is not None and "data" in data["result"]:
            return data["result"]["data"]
    except Exception as e:
        print(f"[WARN] 获取可转债数据失败: {e}")
    return []


def fetch_stocks(page_size=100):
    """获取新股申购数据（含沪深京）"""
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "sortColumns": "APPLY_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": str(page_size),
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
        
        # 尝试新格式：直接 JSON
        try:
            data = resp.json()
        except json.JSONDecodeError:
            # 尝试旧格式：jQuery 回调
            match = re.search(r"jQuery\d+_\d+\((.*)\)", resp.text)
            if match:
                json_text = match.group(1)
                data = json.loads(json_text)
            else:
                print(f"[DEBUG] 响应格式未识别，原文前500字：{resp.text[:500]}")
                return []
        
        if "result" in data and data["result"] is not None and "data" in data["result"]:
            return data["result"]["data"]
    except Exception as e:
        print(f"[WARN] 获取新股数据失败: {e}")
    return []


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
    rating = bond.get("RATING", "")
    issue_size = bond.get("ISSUE_SIZE", "")  # 发行规模(亿)
    apply_code = bond.get("ONLINE_APPLY_CODE", "")  # 申购代码

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
    summary = f"🪙 {name}({code}) 申购"
    desc_parts = [f"名称: {name}", f"代码: {code}"]
    if apply_code:
        desc_parts.append(f"申购代码: {apply_code}")
    if rating:
        desc_parts.append(f"信用评级: {rating}")
    if issue_size:
        desc_parts.append(f"发行规模: {issue_size}亿")
    desc_parts.append("申购时间: 9:15-15:00")
    description = "\\n".join(desc_parts)

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


def build_stock_event(stock):
    """为单只新股生成 VEVENT 块"""
    name = stock.get("SECURITY_NAME_ABBR", stock.get("SECURITY_NAME", "未知新股"))
    code = stock.get("SECURITY_CODE", "")
    apply_code = stock.get("APPLY_CODE", "")
    date_raw = stock.get("APPLY_DATE", "")
    market = stock.get("MARKET", "")  # 沪/深/京
    price = stock.get("PRICE", "") or stock.get("ISSUE_PRICE", "")
    pe = stock.get("PE_RATIO", "") or stock.get("ISSUE_PE", "")
    apply_limit = stock.get("APPLY_LIMIT", "")  # 申购上限

    dt_start = format_date_ics(date_raw)
    if not dt_start:
        return None

    today = datetime.now().strftime("%Y%m%d")
    if dt_start < today:
        return None

    # 计算结束日期（次日）
    start_date = datetime.strptime(dt_start, "%Y%m%d")
    end_date = (start_date + timedelta(days=1)).strftime("%Y%m%d")

    uid = make_uid("stock", code, dt_start)
    summary = f"📈 {name}({code}) 新股申购"
    desc_parts = [f"名称: {name}", f"代码: {code}"]
    if apply_code:
        desc_parts.append(f"申购代码: {apply_code}")
    if market:
        desc_parts.append(f"市场: {market}")
    if price:
        desc_parts.append(f"发行价: {price}元")
    if pe:
        desc_parts.append(f"市盈率: {pe}")
    if apply_limit:
        desc_parts.append(f"申购上限: {apply_limit}股")
    desc_parts.append("沪市: 9:30-11:30/13:00-15:00")
    desc_parts.append("深市: 9:15-11:30/13:00-15:00")
    description = "\\n".join(desc_parts)

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
    stocks = fetch_stocks()
    print(f"[INFO] 获取到 {len(stocks)} 条新股数据")

    # 生成事件
    events = []
    for bond in bonds:
        event = build_bond_event(bond)
        if event:
            events.append(event)

    for stock in stocks:
        event = build_stock_event(stock)
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
