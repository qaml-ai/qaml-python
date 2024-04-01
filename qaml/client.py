from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.webdriver.common.appiumby import AppiumBy
import re
import time
import base64
import subprocess
import json
from PIL import Image
from io import BytesIO
import requests

def get_serial():
    system_profiler_output = subprocess.run(["system_profiler", "SPUSBDataType"], capture_output=True, text=True).stdout
    serial_numbers = re.findall(r'(iPhone|iPad).*?Serial Number: *([^\n]+)', system_profiler_output, re.DOTALL)

    if serial_numbers:
        first_serial_number = serial_numbers[0][1].strip()
        modified_serial_number = first_serial_number[:8] + '-' + first_serial_number[8:]
        return modified_serial_number

class Client:
    def __init__(self, api_key, driver=None):
        self.api_key = api_key
        if not driver:
            options = XCUITestOptions()
            options.udid = get_serial()
            custom_caps = {
                    "mjpegScreenshotUrl": "http://localhost:9100"
            }
            options.load_capabilities(custom_caps)
            try:
                driver = webdriver.Remote('http://localhost:4723', options=options)
            except:
                driver = webdriver.Remote('http://localhost:4723/wd/hub', options=options)
        self.driver = driver
        self.driver.start_recording_screen()
        self.driver.update_settings({'waitForIdleTimeout': 0})
        self.driver.update_settings({'shouldWaitForQuiescence': False})
        self.driver.update_settings({'maxTypingFrequency': 60})

    def tap_coordinates(self, x, y):
        self.driver.execute_script("mobile: tap", {"x": x, "y": y})

    def drag(self, startX, startY, endX, endY):
        self.driver.execute_script("mobile: dragFromToForDuration", {"fromX": startX, "fromY": startY, "toX": endX, "toY": endY, "duration": 1})

    def swipe(self, direction):
        self.driver.execute_script("mobile: swipe", {"direction": direction})

    def scroll(self, direction):
        # reverse direction
        direction_map = {
            "up": "down",
            "down": "up",
            "left": "right",
            "right": "left"
        }
        direction = direction_map[direction]
        self.driver.execute_script("mobile: swipe", {"direction": direction})

    def type_text(self, text):
        application_element = self.driver.find_element(AppiumBy.IOS_PREDICATE, "type == 'XCUIElementTypeApplication'")
        application_element.send_keys(text)

    def sleep(self, seconds):
        time.sleep(seconds)

    def execute(self, script):
        screenshot = self.driver.get_screenshot_as_base64()
        start_time = time.time()
        isKeyboard = self.driver.is_keyboard_shown()

        PIL_image = Image.open(BytesIO(base64.b64decode(screenshot)))
        longer_side = max(PIL_image.size)
        aspect_ratio = PIL_image.size[0] / PIL_image.size[1]
        new_size = (960, int(960 / aspect_ratio)) if PIL_image.size[0] == longer_side else (int(960 * aspect_ratio), 960)
        PIL_image = PIL_image.resize(new_size)
        buffered = BytesIO()
        PIL_image.save(buffered, format="PNG")

        screenshot = base64.b64encode(buffered.getvalue()).decode("utf-8")
        input_elements = []
        payload = {"action": script, "screen_size": self.driver.get_window_size(), "input_elements": input_elements, "screenshot": screenshot}
        response = requests.post("https://api.camelqa.com", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        actions = response.json()
        available_functions = {
            "tap": self.tap_coordinates,
            "drag": self.drag,
            "swipe": self.swipe,
            "scroll": self.scroll,
            "type_text": self.type_text,
            "sleep": self.sleep
        }
        for action in actions:
            function = available_functions[action["name"]]
            arguments = json.loads(action["arguments"])
            function(**arguments)

