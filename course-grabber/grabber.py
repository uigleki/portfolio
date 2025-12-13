from datetime import datetime
from os import path
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.webdriver import WebDriver
from threading import Timer
import time

# University course registration system automation
url = 'https://sys.ndhu.edu.tw/AA/CLASS/subjselect/'

# HTML element IDs
name_input = 'ContentPlaceHolder1_ed_StudNo'
passwd_input = 'ContentPlaceHolder1_ed_pass'
login_btn = 'ContentPlaceHolder1_BtnLoginNew'
logout_btn = 'ContentPlaceHolder1_HyperLink5'
pre_sort_btn = 'ContentPlaceHolder1_Button7'

# XPath template for course add buttons (row index injected)
start_add_btn = '//*[@id="ContentPlaceHolder1_grd_subjs"]/tbody/tr['
end_add_btn = ']/td[1]'

# Alert text patterns
login_error = '帳號或密碼錯誤'
grab_success = '成功'

# Timing configuration
start_hour = 12
start_minute = 30

name = 'YOUR_STUDENT_ID'

def main() -> None:
    input_passwd()
    test_login()

    a_ready_login = alarm()
    a_ready_login.do(ready_login, start_hour, start_minute - 5)

def input_passwd() -> None:
    global passwd
    passwd = input('input your passwd: ')

def test_login() -> None:
    create_driver()
    driver.get(url)
    time.sleep(0.5)

    login(driver)
    time.sleep(0.5)

    driver.find_element(By.ID, pre_sort_btn).click()
    time.sleep(0.5)

    driver.find_element(By.XPATH, start_add_btn + str(2) + end_add_btn).click()
    alert_accept()
    time.sleep(0.5)

    driver.find_element(By.ID, logout_btn).click()
    driver.quit()

def ready_login() -> None:
    """Login and prepare for grabbing at T-1 minute"""
    create_driver()
    driver.get(url)
    time.sleep(0.5)

    login(driver)
    time.sleep(0.5)

    driver.find_element(By.ID, pre_sort_btn).click()
    time.sleep(0.5)

    # Schedule grab at T-1 second for precise timing
    a_grab_lesson = alarm()
    a_grab_lesson.do(grab_lesson, start_hour, start_minute - 1, 59)

def grab_lesson() -> None:
    """Click all pre-sorted courses as fast as possible"""
    i = 2  # Start from row 2 (row 1 is header)
    # Keep clicking row 2 until success (other students may grab first)
    while True:
        driver.find_element(By.XPATH, start_add_btn + str(i) + end_add_btn).click()
        alert_accept()
        if alert_text.find(grab_success) != -1:
            break

    # Click remaining courses in wishlist
    while True:
        i += 1
        try:
            driver.find_element(By.XPATH, start_add_btn + str(i) + end_add_btn).click()
            alert_accept()
        except:
            break

    driver.find_element(By.ID, logout_btn).click()
    driver.quit()

    print('程式結束')

class alarm:
    """Schedule function execution at specific time"""
    def do(self, func, start_hour, start_minute, start_second = 0) -> None:
        time_now = datetime.now()
        time_start = time_now.replace(hour=start_hour, minute=start_minute, second=start_second, microsecond=0)
        time_delta = time_start - time_now
        time_secs = time_delta.total_seconds()

        self.timer = Timer(time_secs, func)
        self.timer.start()

def login(driver) -> None:
    driver.find_element(By.ID, name_input).send_keys(name)
    driver.find_element(By.ID, passwd_input).send_keys(passwd)
    driver.find_element(By.ID, login_btn).click()
    alert_accept()
    if alert_text.find(login_error) != -1:
        driver.quit()
        print('登入失敗')
        exit(1)

def create_driver() -> None:
    global driver
    service = Service(log_path=path.devnull)
    driver = WebDriver(service=service)
    driver.implicitly_wait(5)

def alert_accept() -> None:
    global alert_text
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        print(alert_text)
        alert.accept()
    except:
        alert_text = ''

if __name__ == '__main__':
    main()
