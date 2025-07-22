import os
import time
import zipfile
import tarfile
import logging
import pandas as pd
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EXCEL_FILE = "server_list.xlsx"
BASE_DIR = os.getcwd()
LOG_DIR = os.path.join(BASE_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

def setup_logger(ip):
    log_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"{ip}_{log_time}.log")
    logger = logging.getLogger(ip)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler1 = logging.StreamHandler()
    handler2 = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler1.setFormatter(formatter)
    handler2.setFormatter(formatter)
    logger.addHandler(handler1)
    logger.addHandler(handler2)
    return logger

def selenium_export(driver, wait, ip, username, password, logger):
    LOGIN_URL = f"https://{ip}/#/login"
    logger.info("启动浏览器引擎（后台模式）...")
    driver.get(LOGIN_URL)
    logger.info("正在登录系统...")
    wait.until(EC.presence_of_element_located((By.ID, "login_username"))).send_keys(username)
    driver.find_element(By.ID, "login_password").send_keys(password)
    driver.find_element(By.ID, "login_right_submit_btn").click()
    wait.until(EC.presence_of_element_located((By.ID, "immUser")))
    logger.info("登录成功")
    logger.info("准备导出数据...")
    export_btn = wait.until(EC.element_to_be_clickable((By.ID, "immExport")))
    driver.execute_script("arguments[0].click();", export_btn)
    panel = wait.until(EC.visibility_of_element_located((By.ID, "exportDetailShow")))
    logger.info("选择所有导出项...")
    for cb in panel.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        if not cb.is_selected():
            driver.execute_script("arguments[0].click();", cb)
    radios = panel.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    if radios:
        driver.execute_script("arguments[0].click();", radios[0])
    logger.info("开始导出操作...")
    confirm = panel.find_element(By.XPATH, ".//button[@ng-click='clkExportOk()']")
    driver.execute_script("arguments[0].click();", confirm)
    logger.info("正在生成压缩包，请稍候...")

def wait_for_archive(save_dir, logger, prefix="xcc_export_"):
    MAX_WAIT_DOWNLOAD = 120
    start_time = time.time()
    last_size = 0
    stable_count = 0
    while time.time() - start_time < MAX_WAIT_DOWNLOAD:
        for fn in os.listdir(save_dir):
            if fn.lower().startswith(prefix) and (fn.lower().endswith(".zip") or fn.lower().endswith(".tgz")):
                file_path = os.path.join(save_dir, fn)
                current_size = os.path.getsize(file_path)
                if current_size == last_size:
                    stable_count += 1
                else:
                    stable_count = 0
                    last_size = current_size
                if stable_count >= 2:
                    logger.info(f"下载完成: {fn} (大小: {current_size//1024} KB)")
                    return file_path
        time.sleep(1)
    raise TimeoutError(f"在 {MAX_WAIT_DOWNLOAD} 秒内未检测到完整压缩文件")

def extract_and_cleanup(archive_path, save_dir, logger):
    logger.info(f"正在解压文件: {os.path.basename(archive_path)}")
    extracted_files = []
    if archive_path.lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path, 'r') as z:
            for member in z.namelist():
                if member.lower().endswith((".xls", ".xlsx")):
                    z.extract(member, save_dir)
                    extracted_files.append(member)
                    logger.info(f"  → 提取: {member}")
    elif archive_path.lower().endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.lower().endswith((".xls", ".xlsx")):
                    tar.extract(member, save_dir)
                    extracted_files.append(member.name)
                    logger.info(f"  → 提取: {member.name}")
    os.remove(archive_path)
    logger.info(f"已删除压缩包")
    return extracted_files

def process_server(ip, username, password):
    # 每个服务器一个独立的下载目录
    save_dir = os.path.join(BASE_DIR, ip)
    os.makedirs(save_dir, exist_ok=True)
    logger = setup_logger(ip)
    chrome_opts = Options()
    chrome_opts.add_argument("--ignore-certificate-errors")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--headless")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--window-size=1920,1080")
    prefs = {
        "download.default_directory": save_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
        "profile.default_content_settings.popups": 0
    }
    chrome_opts.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=chrome_opts)
    wait = WebDriverWait(driver, 20)
    try:
        selenium_export(driver, wait, ip, username, password, logger)
        archive_file = wait_for_archive(save_dir, logger)
        excel_files = extract_and_cleanup(archive_file, save_dir, logger)
        logger.info("="*50)
        logger.info("操作成功完成！Excel 文件列表:")
        for f in excel_files:
            logger.info(f"  • {f}")
        logger.info(f"文件保存在: {save_dir}")
        logger.info("="*50)
    except Exception as e:
        logger.error("发生错误: %s", str(e))
        logger.info("="*50)
    finally:
        driver.quit()

if __name__ == "__main__":
    df = pd.read_excel(EXCEL_FILE)
    for _, row in df.iterrows():
        ip = str(row['IP'])
        username = str(row['USERNAME'])
        password = str(row['PASSWORD'])
        process_server(ip, username, password)
