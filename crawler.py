# -*- coding: utf-8 -*-
	
import pandas as pd
from selenium import webdriver
import time
import re
import json
import pickle
import requests
import datetime
import os

# ── 集思录登录 ──────────────────────────────────────────
JISILU_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jisilu_config.json')
JISILU_COOKIE_FILE = os.path.expanduser('~/.jisilu_cookies.pkl')

def jisilu_encode(text, aes_key):
    """AES-128-ECB 加密，PKCS7 填充，输出 hex（与集思录前端 CryptoJS 一致）"""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    key = aes_key.encode('utf-8')
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    data = text.encode('utf-8')
    pad_len = 16 - len(data) % 16
    padded = data + bytes([pad_len] * pad_len)
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return encrypted.hex()

def load_jisilu_config():
    """读取 jisilu_config.json，返回 (username, password, filter_dict)"""
    if not os.path.exists(JISILU_CONFIG):
        print("错误：未找到配置文件 %s" % JISILU_CONFIG)
        print("请创建该文件，内容示例：")
        print('  {"username": "手机号", "password": "密码", "filter": {...}}')
        exit(1)
    try:
        with open(JISILU_CONFIG) as f:
            cfg = json.load(f)
        username = cfg['username']
        password = cfg['password']
        flt = cfg.get('filter', {})
        return username, password, flt
    except Exception as e:
        print("错误：配置文件格式不正确：%s" % e)
        exit(1)

def jisilu_login(username, password):
    """集思录用户名密码登录，返回带 cookies 的 Session"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Origin': 'https://www.jisilu.cn',
        'Referer': 'https://www.jisilu.cn/login/',
        'X-Requested-With': 'XMLHttpRequest',
    })
    # 获取登录页，取 AES key
    r = s.get('https://www.jisilu.cn/login/', timeout=15)
    key_match = re.search(r"var key\s*=\s*[\"']([^\"']*)[\"']", r.text)
    if not key_match:
        print('错误：无法从登录页获取 AES key')
        return None
    aes_key = key_match.group(1)
    # 加密后 POST 登录
    login_data = {
        'return_url': '/',
        'user_name': jisilu_encode(username, aes_key),
        'password': jisilu_encode(password, aes_key),
        'aes': '1',
        'auto_login': '1',
    }
    r2 = s.post('https://www.jisilu.cn/webapi/account/login_process/',
                data=login_data, timeout=15)
    try:
        result = r2.json()
    except Exception:
        print('登录失败：服务器返回异常')
        return None
    if result.get('code') == 200:
        print('集思录登录成功')
        os.makedirs(os.path.dirname(JISILU_COOKIE_FILE) or '.', exist_ok=True)
        with open(JISILU_COOKIE_FILE, 'wb') as f:
            pickle.dump(dict(s.cookies), f)
        return s
    else:
        msg = result.get('msg', '未知错误')
        print('集思录登录失败：%s' % msg)
        if result.get('data', {}).get('captcha'):
            print('提示：触发验证码，登录环境变更后重试')
        return None

def ensure_jisilu_session():
    """返回有效 Session：优先用缓存，失效则重新登录"""
    # 尝试缓存
    if os.path.exists(JISILU_COOKIE_FILE):
        try:
            with open(JISILU_COOKIE_FILE, 'rb') as f:
                cookies = pickle.load(f)
            s = requests.Session()
            s.cookies.update(cookies)
            s.headers.update({'User-Agent': 'Mozilla/5.0'})
            r = s.get('https://www.jisilu.cn/', timeout=10)
            if r.status_code == 200:
                print('使用缓存的登录状态')
                return s
        except Exception:
            pass
    # 重新登录
    username, password, _ = load_jisilu_config()
    sess = jisilu_login(username, password)
    return sess

def get_browser(url):
    options = webdriver.ChromeOptions()
    #options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=options)


    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                          get: () => undefined
                        })
                      """
    })
    
    # 集思录登录：requests + AES 程序化登录，无需手动登录
    sess = ensure_jisilu_session()
    if sess is None:
        raise RuntimeError('集思录登录失败，请检查 jisilu_config.json 配置')
    set_cookie(driver, sess)

    return driver


def set_cookie(driver, sess):
    """将登录得到的 cookies 注入 Selenium 浏览器"""
    driver.get('https://www.jisilu.cn/')
    for cookie in sess.cookies:
        if not cookie.name or not cookie.value:
            continue
        driver.add_cookie({
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'path': cookie.path,
        })

def convert_float(rt1,rt2):
		ratio1 = float(rt1.strip('%'))
		ratio2 = float(rt2.strip('%'))
		return ratio1,ratio2


if __name__=='__main__':
			url = 'https://www.jisilu.cn/web/data/cb/delisted'
			browser = get_browser(url)
						
			browser.get(url)
			time.sleep(10)
			data = browser.page_source
			tables = pd.read_html(data,header=None)
			print(f"tables[0]:{tables[0]}")
			print(f"tables[1]:{tables[1]}")
			
			
			column1 = tables[1].columns.tolist()
			column0 = tables[0].columns.tolist()
			zipped = zip(column1, column0)
			#使用dict()函数将元组列表转换为字典
			dictionary = dict(zipped)
			print(f"column1:{column1},column0:{column0},dictionary:{dictionary}")
			jsl_df_raw = tables[1].rename(columns=dictionary)
			jsl_df = jsl_df_raw.rename(columns={'发行规模(亿元)': '发行规模', '回售规模(亿元)': '回售规模','剩余规模(亿元)': '剩余规模','存续年限(年)': '存续年限'})

			#print(f"jsl_df:{jsl_df}")
			
			tnow = datetime.datetime.now()
			print("time is :" + tnow.strftime('%Y%m%d'))
			filein = tnow.strftime('%Y_%m_%d') + '_in.xlsx'
			getakpath =  "./%s" % (filein)
			jsl_df.replace('-','0',inplace=True)
			
			#修改名称
			
			#jsl_df.to_excel(getakpath,header=['代码','名称','最后交易价格', '正股代码','正股名称', '发行规模','回售规模','剩余规模', '发行日期','最后交易日', '到期日期','存续年限','退市原因'],index=False,sheet_name='jsl')
			jsl_df.to_excel(getakpath,index=False,sheet_name='jsl')
			print("data of path:" + getakpath)
