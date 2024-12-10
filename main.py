import pandas as pd
from typing import Dict, List
import requests
import json
from datetime import datetime
import time
import pytz

API_SLEEP_TIME = 2
API_TOKEN = ""
JSON_NAME = "call.json"

def get_ticker_from_pump(address:str) -> str:
    for _ in range(0,3):
        try:
            url = f"https://frontend-api.pump.fun/coins/{address}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()["symbol"]
        except:
            time.sleep(API_SLEEP_TIME)
    return ""

def get_ticker_from_dexscreener(address:str) -> str:
    for _ in range(0,3):
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={address}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()["pairs"][0]["baseToken"]["symbol"]
        except:
            time.sleep(API_SLEEP_TIME)
    return ""

def get_ticker(token_address:str) -> str:
    ticker = get_ticker_from_pump(token_address)
    if ticker != "":
        return ticker

    ticker = get_ticker_from_dexscreener(token_address)
    if ticker != "":
        return ticker

    return ""

def format_timestamp(timestamp: int) -> str:
    """
    需要注意：最后我是添加了UTC+8的时间区
    """
    utc_time = datetime.utcfromtimestamp(timestamp)
    tz = pytz.timezone('Asia/Shanghai')
    local_time = utc_time.replace(tzinfo=pytz.UTC).astimezone(tz)
    formatted_time = local_time.strftime('%m月%d日 %H:%M')
    return formatted_time
def fetch_chart_data(base, api_token, time_from, time_to):
    url = "https://api-edge.bullx.io/chart"

    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": f"Bearer {api_token}",
        "content-type": "text/plain",
        "sec-ch-ua": "\"Chromium\";v=\"128\", \"Not;A=Brand\";v=\"24\", \"Google Chrome\";v=\"128\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "Referer": "https://bullx.io/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    payload = {
        "name": "chart",
        "data": {
            "chainId": 1399811149,
            "base": base,
            "quote": "So11111111111111111111111111111111111111112",
            "from": time_from,
            "to": time_to,
            "intervalSecs": 60,
        }
    }

    for _ in range(0,3):
        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"错误: {e}")
            time.sleep(2)
    raise

def write_to_excel(data: List[Dict], filename: str = 'output.xlsx'):
    df = pd.DataFrame(data)
    df.to_excel(filename, index=False)
    print(f"数据已保存至 {filename}")

def load_data_call():
    try:
        with open(JSON_NAME, 'r') as file:
            data = json.load(file)
            print(f"成功读取{len(data)}条数据")
            return data
    except FileNotFoundError:
        print("call.json 文件未找到")
        raise
    except json.JSONDecodeError:
        print("call.json 文件格式错误")
        raise


data_call = sorted(load_data_call(), key=lambda x: x['timestamp_call'])

if __name__ == "__main__":
    timestamp_now = int(time.time())
    print(f"当前时间：{format_timestamp(timestamp_now)}")
    print("")

    collected_data = []
    data_call_len = len(data_call)
    for i, call in enumerate(data_call):
        token_address = call["token_address"]
        timestamp_call = call["timestamp_call"]
        ticker = get_ticker(token_address)
        print(f"({i+1}/{data_call_len}) ${ticker} {format_timestamp(timestamp_call)} | {token_address}")
        chart_data = fetch_chart_data(token_address, API_TOKEN, timestamp_call, timestamp_now)

        if chart_data:
            # 获取初始价格（第一个开盘价）和对应时间
            initial_price = chart_data['o'][0]
            initial_time = format_timestamp(int(chart_data['t'][0] / 1000))

            # 获取最低价和对应时间
            lowest_price = min(chart_data['l'])
            lowest_time_index = chart_data['l'].index(lowest_price)
            lowest_time = format_timestamp(int(chart_data['t'][lowest_time_index] / 1000))

            # 获取最高价和对应时间
            highest_price = max(chart_data['h'])
            highest_time_index = chart_data['h'].index(highest_price)
            highest_time = format_timestamp(int(chart_data['t'][highest_time_index] / 1000))

            # 获取当前价格（最后一个收盘价）和对应时间
            current_price = chart_data['c'][-1]
            current_time = format_timestamp(int(chart_data['t'][-1] / 1000))

            # 计算各种收益率
            max_profit_rate = ((highest_price - initial_price) / initial_price) * 100
            max_loss_rate = ((lowest_price - initial_price) / initial_price) * 100
            current_profit_rate = ((current_price - initial_price) / initial_price) * 100

            print(f"喊单价格: {initial_price:.10f} ({initial_time})")
            print(f"最低价格: {lowest_price:.10f} ({lowest_time})")
            print(f"最高价格: {highest_price:.10f} ({highest_time})")
            print(f"当前价格: {current_price:.10f} ({current_time})")
            print(f"最高收益率: {max_profit_rate:.2f}%")
            print(f"最大亏损率: {max_loss_rate:.2f}%")
            print(f"当前收益率: {current_profit_rate:.2f}%")
            print("")

            data_entry = {
                "ticker": ticker,
                "token_address": token_address,
                "call_time": format_timestamp(timestamp_call),
                "initial_price": initial_price,
                "initial_time": initial_time,
                "lowest_price": lowest_price,
                "lowest_time": lowest_time,
                "highest_price": highest_price,
                "highest_time": highest_time,
                "current_price": current_price,
                "current_time": current_time,
                "max_profit_rate": max_profit_rate,
                "max_loss_rate": max_loss_rate,
                "current_profit_rate": current_profit_rate
            }
            collected_data.append(data_entry)
        else:
            print("无法获取K线数据，请重新抓取 bullx Token")
            break
    write_to_excel(collected_data)