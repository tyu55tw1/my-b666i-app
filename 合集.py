import streamlit as st
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
from collections import Counter
import random
import itertools
import urllib3
import time
from datetime import datetime
import xml.etree.ElementTree as ET
import yfinance as yf
import twstock

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 頁面設定
# ==========================================
st.set_page_config(
    page_title="全能 AI 助理 (網頁旗艦版)",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 核心演算法區 (LogicCore - 保持不變)
# ==========================================
class LogicCore:
    WEATHER_API_KEY = "E3e2c14f7956d939b88a6dfa66e4f10a"
    CITY_MAPPING = {
        "台北": "Taipei", "新北": "New Taipei", "板橋": "Banqiao", "桃園": "Taoyuan",
        "新竹": "Hsinchu", "苗栗": "Miaoli", "台中": "Taichung", "彰化": "Changhua",
        "南投": "Nantou", "雲林": "Yunlin", "嘉義": "Chiayi", "台南": "Tainan",
        "高雄": "Kaohsiung", "屏東": "Pingtung", "宜蘭": "Yilan", "花蓮": "Hualien",
        "台東": "Taitung", "澎湖": "Penghu", "金門": "Kinmen", "基隆": "Keelung"
    }

    @staticmethod
    def fetch_bingo_data():
        url = "https://www.pilio.idv.tw/bingo/list.asp"
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            res = requests.get(url, headers=headers, timeout=10, verify=False)
            res.encoding = 'big5'
            soup = BeautifulSoup(res.text, 'html.parser')
            data = []
            seen = set()
            for row in soup.find_all('tr'):
                text = row.get_text(strip=True)
                id_match = re.search(r'(11[3-9]\d{6})', text)
                if id_match:
                    draw_id = int(id_match.group(1))
                    if draw_id in seen: continue
                    nums = [int(n) for n in re.findall(r'\d+', text) if int(n) <= 80 and int(n) != draw_id]
                    if len(nums) >= 20:
                        data.append({"期數": draw_id, "號碼": nums[:20]})
                        seen.add(draw_id)
            return pd.DataFrame(data).sort_values("期數", ascending=False).reset_index(drop=True)
        except Exception as e:
            st.error(f"連線錯誤: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_bingo_stats(df, periods=50):
        if df.empty: return [], []
        subset = df.head(periods)
        all_nums = [n for sublist in subset['號碼'] for n in sublist]
        counts = Counter(all_nums)
        hot = counts.most_common(10)
        cold = []
        for i in range(1, 81):
            if i not in counts: cold.append((i, 0))
            else: cold.append((i, counts[i]))
        cold.sort(key=lambda x: x[1])
        return hot, cold[:10]

    @staticmethod
    def get_bingo_prize(star, hits):
        table = {
            1: {1: 50}, 2: {1: 25, 2: 75}, 3: {2: 50, 3: 500},
            4: {2: 25, 3: 100, 4: 1000}, 5: {3: 50, 4: 500, 5: 7500},
            6: {3: 25, 4: 200, 5: 1000, 6: 25000}, 
            7: {3: 25, 4: 50, 5: 300, 6: 3000, 7: 80000},
            8: {4: 25, 5: 100, 6: 800, 7: 20000, 8: 500000}, 
            9: {4: 25, 5: 100, 6: 1000, 7: 3000, 8: 100000, 9: 1000000},
            10: {5: 25, 6: 100, 7: 1000, 8: 5000, 9: 25000, 10: 5000000}
        }
        return table.get(star, {}).get(hits, 0)

    @staticmethod
    def fetch_lotto_data(type_name):
        pages = 3
        if "大樂透" in type_name: base_url = "https://www.pilio.idv.tw/ltobig/list.asp"; min_n = 7
        elif "威力彩" in type_name: base_url = "https://www.pilio.idv.tw/lto/list.asp"; min_n = 7
        elif "539" in type_name: base_url = "https://www.pilio.idv.tw/lto539/list.asp"; min_n = 5
        
        all_data = []
        headers = {"User-Agent": "Mozilla/5.0"}
        for p in range(1, pages + 1):
            try:
                r = requests.get(f"{base_url}?indexpage={p}", headers=headers, timeout=5)
                r.encoding = 'big5'
                txt = re.sub(r'<[^>]+>', ' ', r.text)
                pat_a = re.compile(r'(\d{2}/\d{2})\s+(\d{2})')
                matches = []
                for m in pat_a.finditer(txt): matches.append({"s": m.end()})
                matches.sort(key=lambda x: x['s'])
                for i, m in enumerate(matches):
                    end = matches[i+1]['s'] if i < len(matches)-1 else len(txt)
                    nums = re.findall(r'\b\d{2}\b', txt[m['s']:end])
                    if len(nums) >= min_n:
                        entry = {"特別號": nums[min_n-1] if "539" not in type_name else "無"}
                        all_data.append(entry)
            except: continue
        if all_data: return pd.DataFrame(all_data)
        return None

    @staticmethod
    def calculate_ac(numbers):
        r = len(numbers)
        diffs = set()
        for pair in itertools.combinations(numbers, 2):
            diffs.add(abs(pair[0] - pair[1]))
        return len(diffs) - (r - 1)

    @staticmethod
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0: return False
        return True

    @staticmethod
    def generate_tickets(l_type, count):
        if "大樂透" in l_type: max_n, pick = 49, 6
        elif "威力彩" in l_type: max_n, pick = 38, 6
        elif "539" in l_type: max_n, pick = 39, 5
        
        tickets = []
        attempts = 0
        max_attempts = 50000 
        primes = [n for n in range(1, max_n+1) if LogicCore.is_prime(n)]
        
        while len(tickets) < count and attempts < max_attempts:
            attempts += 1
            combo = sorted(random.sample(range(1, max_n+1), pick))
            s = sum(combo)
            if "大樂透" in l_type and not (115 <= s <= 185): continue
            if "威力彩" in l_type and not (85 <= s <= 145): continue
            if "539" in l_type and not (75 <= s <= 125): continue
            ac = LogicCore.calculate_ac(combo)
            min_ac = 7 if pick == 6 else 4
            if ac < min_ac: continue
            odds = sum(1 for n in combo if n%2!=0)
            if pick == 6 and odds not in [3, 2, 4]: continue
            if pick == 5 and odds not in [2, 3]: continue
            prime_count = sum(1 for n in combo if n in primes)
            if not (1 <= prime_count <= 3): continue
            if combo not in [t['nums'] for t in tickets]:
                tickets.append({"nums": combo, "ac": ac, "sum": s})
        return tickets

# ==========================================
# 工具函數 (Utils)
# ==========================================
def get_weather_icon(desc):
    desc = desc.lower()
    if "雷" in desc: return "⛈️"
    if "雪" in desc: return "❄️"
    if "雨" in desc: return "🌧️"
    if "雲" in desc or "陰" in desc: return "☁️"
    if "晴" in desc: return "☀️"
    return "⛅"

def get_clothing_advice(temp, rain_prob):
    try:
        temp = int(temp)
        advice = ""
        if temp >= 30: advice = "🔥 非常炎熱！穿短袖、短褲，多喝水。"
        elif 25 <= temp < 30: advice = "😎 天氣熱，建議穿著透氣的短袖。"
        elif 20 <= temp < 25: advice = "😊 舒適宜人，穿短袖搭配薄外套。"
        elif 15 <= temp < 20: advice = "🍃 有點涼意，建議穿長袖、帽T。"
        elif 10 <= temp < 15: advice = "🧥 寒冷，請穿厚外套、毛衣。"
        else: advice = "🥶 極冷！羽絨衣全副武裝！"
        
        rp = 0
        if str(rain_prob).isdigit(): rp = int(rain_prob)
        elif ">" in str(rain_prob): rp = 50
        
        if rp >= 40: advice += " (記得帶傘 ☔)"
        return advice
    except: return "數據分析中..."

# ==========================================
# 介面佈局 (Main UI)
# ==========================================
st.title("🤖 全能 AI 助理 (網頁版)")
st.caption("集成 天氣 / 賓果 / 樂透 / 網搜 / 股市 / 發票 / 匯率")

# 使用 Tabs 分頁
tabs = st.tabs(["⛅ 氣象", "🎰 賓果AI", "💰 賓果損益", "🏆 樂透", "🔎 網搜", "📈 股市", "🧾 發票", "💱 匯率"])

# --- Tab 1: 氣象 ---
with tabs[0]:
    st.header("迷你氣象站")
    col1, col2 = st.columns([3, 1])
    with col1:
        city_input = st.text_input("輸入城市名稱 (例如: 台北, Tokyo)", "Taipei")
    with col2:
        search_btn = st.button("查詢天氣", type="primary")

    if search_btn:
        with st.spinner("連線氣象衛星中..."):
            # 轉換城市名
            search_city = city_input
            for tw, en in LogicCore.CITY_MAPPING.items():
                if tw in city_input: search_city = en; break
            
            # 策略 A: OpenWeatherMap
            success = False
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={search_city}&appid={LogicCore.WEATHER_API_KEY}&units=metric&lang=zh_tw"
                r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    temp = data['main']['temp']
                    desc = data['weather'][0]['description']
                    icon = get_weather_icon(desc)
                    humid = data['main']['humidity']
                    rain = ">40%" if 'rain' in data else "0%"
                    advice = get_clothing_advice(temp, 50 if 'rain' in data else 0)
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("溫度", f"{int(temp)}°C")
                    c2.metric("濕度", f"{humid}%")
                    c3.metric("天氣", desc)
                    st.info(f"{icon} 穿衣建議: {advice}")
                    success = True
            except: pass

            # 策略 B: wttr.in
            if not success:
                try:
                    url = f"https://wttr.in/{search_city}?format=j1&lang=zh-tw"
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        cur = data['current_condition'][0]
                        temp = cur['temp_C']
                        desc = cur['lang_zh-tw'][0]['value']
                        
                        c1, c2, c3 = st.columns(3)
                        c1.metric("溫度", f"{temp}°C")
                        c2.metric("體感", f"{cur['FeelsLikeC']}°C")
                        c3.metric("天氣", desc)
                        st.info(f"{get_weather_icon(desc)} 穿衣建議: {get_clothing_advice(temp, 0)}")
                    else:
                        st.error("查無此城市，請輸入英文名稱試試。")
                except:
                    st.error("連線失敗，請稍後再試。")

# --- Tab 2: 賓果 AI ---
with tabs[1]:
    st.header("賓果賓果 AI 預測")
    
    if 'bingo_df' not in st.session_state:
        st.session_state.bingo_df = pd.DataFrame()
        st.session_state.hot = []
        st.session_state.cold = []

    if st.button("🔄 載入/更新最新開獎資料"):
        with st.spinner("正在爬取歷史資料..."):
            df = LogicCore.fetch_bingo_data()
            if not df.empty:
                st.session_state.bingo_df = df
                st.session_state.hot, st.session_state.cold = LogicCore.get_bingo_stats(df)
                st.success(f"更新成功！最新期數: {df.iloc[0]['期數']}")
            else:
                st.error("資料載入失敗")

    if not st.session_state.bingo_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            stars = st.slider("選擇星數", 1, 10, 3)
            strategy = st.selectbox("自動選號策略", ["手動輸入", "🔥 追擊熱門", "❄️ 抄底冷門", "⚖️ 冷熱平衡"])
        
        # 產生建議號碼
        suggested_nums = []
        if strategy == "🔥 追擊熱門":
            suggested_nums = [x[0] for x in st.session_state.hot[:stars]]
        elif strategy == "❄️ 抄底冷門":
            suggested_nums = [x[0] for x in st.session_state.cold[:stars]]
        elif strategy == "⚖️ 冷熱平衡":
            half = stars // 2
            suggested_nums = [x[0] for x in st.session_state.hot[:half]] + [x[0] for x in st.session_state.cold[:(stars-half)]]
        
        user_input = st.text_input("您的選號 (用空白分隔)", value=" ".join(map(str, suggested_nums)))
        
        # 回測
        backtest_period = st.selectbox("回測期數", [10, 20, 50, 100], index=1)
        if st.button("🚀 開始回測"):
            try:
                u_nums = [int(n) for n in user_input.split()]
                if len(u_nums) != stars:
                    st.warning(f"請輸入 {stars} 個號碼")
                else:
                    target_df = st.session_state.bingo_df.head(backtest_period)
                    results = []
                    total_hits = 0
                    win_count = 0
                    for _, row in target_df.iterrows():
                        draw_nums = set(row['號碼'])
                        hits = len(set(u_nums) & draw_nums)
                        total_hits += hits
                        is_win = hits >= (stars / 2 + 0.5)
                        if is_win: win_count += 1
                        results.append({
                            "期數": row['期數'],
                            "開獎號碼": str(row['號碼']),
                            "命中": hits,
                            "結果": "🎉" if is_win else "❌"
                        })
                    
                    st.dataframe(pd.DataFrame(results))
                    st.info(f"回測 {backtest_period} 期 | 平均命中: {total_hits/backtest_period:.2f} | 勝率: {(win_count/backtest_period)*100:.1f}%")
            except:
                st.error("號碼格式錯誤")

# --- Tab 3: 賓果損益 ---
with tabs[2]:
    st.header("賓果損益試算")
    if st.session_state.bingo_df.empty:
        st.warning("請先至「賓果AI」分頁載入資料")
    else:
        c1, c2, c3 = st.columns(3)
        star_chk = c1.number_input("玩法星數", 1, 10, 3)
        mult = c2.number_input("倍數", 1, 100, 1)
        nums_chk = st.text_input("投注號碼 (空白分隔)", key="checker_input")
        
        if st.button("計算損益"):
            try:
                my_nums = [int(x) for x in nums_chk.split()]
                cost = 25 * mult
                total_cost = 0
                total_win = 0
                history = []
                
                # 預設回測最近 50 期
                target_df = st.session_state.bingo_df.head(50)
                
                for _, row in target_df.iterrows():
                    hits = len(set(my_nums) & set(row['號碼']))
                    prize = LogicCore.get_bingo_prize(star_chk, hits) * mult
                    total_cost += cost
                    total_win += prize
                    history.append([row['期數'], hits, f"${prize}", f"${prize-cost}"])
                
                net = total_win - total_cost
                st.metric("淨利", f"${net}", delta_color="normal" if net >= 0 else "inverse")
                st.dataframe(pd.DataFrame(history, columns=["期數", "命中", "獎金", "損益"]))
            except:
                st.error("輸入錯誤")

# --- Tab 4: 樂透 (已修正為 6 組) ---
with tabs[3]:
    st.header("樂透結構 AI")
    lotto_type = st.radio("選擇彩種", ["大樂透", "威力彩", "今彩539"], horizontal=True)
    if st.button("生成 AI 結構注單"):
        with st.spinner("正在計算最佳 AC 值與質數結構..."):
            # 【修正】：將 5 改為 6，生成 6 組號碼
            tickets = LogicCore.generate_tickets(lotto_type, 6)
            
            # 嘗試抓特別號
            spec_pool = []
            try:
                df = LogicCore.fetch_lotto_data(lotto_type)
                if df is not None: spec_pool = [int(x) for x in df['特別號'] if str(x).isdigit()]
            except: pass
            
            for i, t in enumerate(tickets):
                nums = t['nums']
                spec = ""
                if "威力彩" in lotto_type:
                    s = Counter(spec_pool[:20]).most_common(1)[0][0] if spec_pool else random.randint(1, 8)
                    spec = f" + {s:02d}"
                
                st.markdown(f"**第 {i+1} 注:** `{str(nums)}{spec}`")
                st.caption(f"AC值: {t['ac']} | 總和: {t['sum']}")
                st.divider()

# --- Tab 5: 網搜 ---
with tabs[4]:
    st.header("極速網搜")
    keyword = st.text_input("輸入關鍵字")
    if st.button("搜尋"):
        with st.spinner("Searching..."):
            try:
                url = "https://html.duckduckgo.com/html/"
                r = requests.post(url, data={'q': keyword}, headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(r.text, 'html.parser')
                for link in soup.find_all('a', class_='result__a'):
                    title = link.get_text(strip=True)
                    href = link.get('href')
                    if href and 'duckduckgo' not in href:
                         # 解碼 URL
                         href = urllib.parse.unquote(href).replace('//duckduckgo.com/l/?uddg=', '').split('&')[0]
                         st.markdown(f"#### [{title}]({href})")
                         st.divider()
            except Exception as e:
                st.error(f"搜尋失敗: {e}")

# --- Tab 6: 股市 ---
with tabs[5]:
    st.header("台股監控")
    stock_code = st.text_input("輸入代號 (例如: 2330, 00878)", "00878")
    if st.button("取得報價"):
        with st.spinner("連線證交所..."):
            try:
                # 取得名稱
                name = stock_code
                if stock_code in twstock.codes:
                    name = twstock.codes[stock_code].name
                
                suffix = ".TWO" if stock_code in twstock.codes and twstock.codes[stock_code].market == "上櫃" else ".TW"
                ticker = yf.Ticker(f"{stock_code}{suffix}")
                
                # 價格
                fi = ticker.fast_info
                price = fi.last_price
                prev = fi.previous_close
                change = price - prev
                pct = (change / prev) * 100
                
                # 配息
                try:
                    divs = ticker.dividends
                    last_div = f"{divs.iloc[-1]:.3f}" if not divs.empty else "無"
                    ex_date = str(divs.index[-1].date()) if not divs.empty else "-"
                except: last_div, ex_date = "-", "-"

                col1, col2 = st.columns(2)
                col1.metric(f"{name} ({stock_code})", f"{price:.2f}", f"{change:.2f} ({pct:.2f}%)")
                col2.metric("最新配息", last_div, f"除息日: {ex_date}")
                
                st.write(f"今日範圍: {fi.day_low} - {fi.day_high}")
            except Exception as e:
                st.error(f"查無資料: {e}")

# --- Tab 7: 發票 (格式優化與自動保存) ---
with tabs[6]:
    st.header("發票對獎")
    if st.button("更新本期號碼"):
        try:
            r = requests.get("https://invoice.etax.nat.gov.tw/invoice.xml")
            r.encoding = 'utf-8'
            root = ET.fromstring(r.text)
            item = root.find(".//item")
            desc = item.find("description").text
            
            # 優化格式顯示
            formatted_desc = desc.replace("<p>", "\n\n### ").replace("</p>", "").replace("：", " : ")
            
            st.session_state.invoice_desc_raw = desc
            st.session_state.invoice_desc_view = formatted_desc
            st.session_state.invoice_updated = True
            
        except: st.error("連線失敗")
    
    if 'invoice_updated' in st.session_state and st.session_state.invoice_updated:
        st.info("💡 財政部最新號碼公告：")
        st.markdown(st.session_state.invoice_desc_view)
        
        st.divider()
        st.subheader("快速對獎")
        inv_input = st.text_input("輸入末三碼", max_chars=3)
        if inv_input and len(inv_input) == 3:
            if 'invoice_desc_raw' in st.session_state:
                if inv_input in st.session_state.invoice_desc_raw:
                    st.success("🎉 恭喜！有機會中獎喔！請仔細核對上方完整號碼。")
                    st.balloons()
                else:
                    st.warning("沒中，再接再厲。")

# --- Tab 8: 匯率 (狀態修復版) ---
with tabs[7]:
    st.header("台銀匯率")
    
    if 'currency_df' not in st.session_state:
        st.session_state.currency_df = None

    if st.button("更新匯率表"):
        try:
            dfs = pd.read_html("https://rate.bot.com.tw/xrt?Lang=zh-TW")
            df = dfs[0]
            df = df.iloc[:, :5] # 取前幾欄
            df.columns = ["幣別", "現金買入", "現金賣出", "即期買入", "即期賣出"]
            st.session_state.currency_df = df
        except:
            st.error("無法讀取匯率表")

    if st.session_state.currency_df is not None:
        st.dataframe(st.session_state.currency_df)
        
        st.divider()
        st.subheader("💰 換算計算機")
        
        col1, col2 = st.columns(2)
        with col1:
            rate = st.number_input("匯率 (請參考上方賣出價)", value=32.0, step=0.1)
        with col2:
            usd = st.number_input("外幣金額", value=100, step=10)
            
        twd = int(rate * usd)
        st.success(f"約等於台幣: **${twd:,}** 元")