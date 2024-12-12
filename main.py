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

def get_nmin_timestamp(timestamp_call: int, minutes: int) -> int:
    return timestamp_call + (minutes * 60)

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


def chart_data_filter(chart_data: dict, timestamp_call: int, timestamp_end: int = None) -> dict:
    # 将秒级时间戳转换为毫秒级
    timestamp_call_ms = timestamp_call * 1000
    timestamp_end_ms = timestamp_end * 1000 if timestamp_end else None

    # 找出需要保留的数据的起始索引
    start_index = -1
    end_index = len(chart_data['t']) if timestamp_end_ms is None else -1

    for i, t in enumerate(chart_data['t']):
        if start_index == -1 and t >= timestamp_call_ms:
            start_index = i
        if timestamp_end_ms and t > timestamp_end_ms:
            end_index = i
            break

    # 如果没有找到符合条件的数据，返回空
    if start_index == -1:
        return {}

    # 创建新的数据字典，截取所有数组从start_index到end_index的数据
    new_chart_data = {
        't': chart_data['t'][start_index:end_index],
        'o': chart_data['o'][start_index:end_index],
        'h': chart_data['h'][start_index:end_index],
        'l': chart_data['l'][start_index:end_index],
        'c': chart_data['c'][start_index:end_index],
        'v': chart_data['v'][start_index:end_index]
    }

    return new_chart_data

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
    TWELVE_HOURS = 12 * 60 * 60  # 12小时的秒数

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

    # 初始化合并后的数据结构
    merged_data = {'t': [], 'o': [], 'h': [], 'l': [], 'c': [], 'v': []}

    current_time = time_from
    while current_time < time_to:
        # 计算当前批次的结束时间
        batch_end = min(current_time + TWELVE_HOURS, time_to)

        payload = {
            "name": "chart",
            "data": {
                "chainId": 1399811149,
                "base": base,
                "quote": "So11111111111111111111111111111111111111112",
                "from": current_time,
                "to": batch_end,
                "intervalSecs": 60,
            }
        }

        for _ in range(0, 3):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    data=json.dumps(payload)
                )
                response.raise_for_status()
                batch_data = response.json()

                # 合并数据
                if batch_data and all(key in batch_data for key in ['t', 'o', 'h', 'l', 'c', 'v']):
                    for key in merged_data:
                        merged_data[key].extend(batch_data[key])
                break
            except requests.exceptions.RequestException as e:
                print(f"错误: {e}")
                time.sleep(2)
                continue

        # 更新时间窗口
        current_time = batch_end
        time.sleep(API_SLEEP_TIME)  # 添加延迟避免请求过快

    return merged_data

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
    timestamp_end = 1733961600
    print(f"回测终止时间：{format_timestamp(timestamp_end)}")
    print("")

    # 初始化不同时间窗口的数据列表，增加0min
    time_windows = {
        "0min": [],  # 新增原始数据
        "2min": [],
        "3min": [],
        "4min": [],
        "5min": []
    }

    data_call_len = len(data_call)
    for i, call in enumerate(data_call):
        token_address = call["token_address"]
        timestamp_call = call["timestamp_call"]
        ticker = get_ticker(token_address)
        print(f"({i + 1}/{data_call_len}) ${ticker} {format_timestamp(timestamp_call)} | {token_address}")

        # 获取原始chart数据
        chart_data = fetch_chart_data(token_address, API_TOKEN, timestamp_call, int(time.time()))

        # 为每个时间窗口创建数据（包括0min）
        for minutes, data_list in zip([0, 2, 3, 4, 5], time_windows.values()):
            # 对于0min使用原始数据，其他情况计算n分钟后的时间戳
            timestamp_n_min = timestamp_call if minutes == 0 else get_nmin_timestamp(timestamp_call, minutes)

            # 过滤数据到指定时间范围
            chart_data_filtered = chart_data_filter(chart_data, timestamp_n_min, timestamp_end)

            if chart_data_filtered:
                # 获取初始价格和时间
                initial_price = chart_data_filtered['o'][0]
                initial_time = format_timestamp(int(chart_data_filtered['t'][0] / 1000))

                # 获取最低价和时间
                lowest_price = min(chart_data_filtered['l'])
                lowest_time_index = chart_data_filtered['l'].index(lowest_price)
                lowest_time = format_timestamp(int(chart_data_filtered['t'][lowest_time_index] / 1000))

                # 获取最高价和时间
                highest_price = max(chart_data_filtered['h'])
                highest_time_index = chart_data_filtered['h'].index(highest_price)
                highest_time = format_timestamp(int(chart_data_filtered['t'][highest_time_index] / 1000))

                # 获取最终价格和时间
                current_price = chart_data_filtered['c'][-1]
                current_time = format_timestamp(int(chart_data_filtered['t'][-1] / 1000))

                # 计算收益率
                max_profit_rate = ((highest_price - initial_price) / initial_price) * 100
                max_loss_rate = ((lowest_price - initial_price) / initial_price) * 100
                current_profit_rate = ((current_price - initial_price) / initial_price) * 100

                window_name = "全部数据" if minutes == 0 else f"{minutes}分钟窗口"
                print(f"\n{window_name}:")
                print(f"喊单价格: {initial_price:.10f} ({initial_time})")
                print(f"最低价格: {lowest_price:.10f} ({lowest_time})")
                print(f"最高价格: {highest_price:.10f} ({highest_time})")
                print(f"最终价格: {current_price:.10f} ({current_time})")
                print(f"最高收益率: {max_profit_rate:.2f}%")
                print(f"最大亏损率: {max_loss_rate:.2f}%")
                print(f"最终收益率: {current_profit_rate:.2f}%")

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
                data_list.append(data_entry)
            else:
                window_name = "全部数据" if minutes == 0 else f"{minutes}分钟窗口"
                print(f"{window_name}: 无有效数据")

        print("\n" + "=" * 50 + "\n")

    # 将每个时间窗口的数据保存到单独的Excel文件
    for minutes, data_list in time_windows.items():
        filename = f'output_{minutes}.xlsx'
        write_to_excel(data_list, filename)