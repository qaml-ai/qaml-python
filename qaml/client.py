from appium import webdriver
from appium.options.ios import XCUITestOptions
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
import re
import time
import base64
import subprocess
import json
from PIL import Image
from io import BytesIO
import requests

class BaseClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.driver = None
        self.platform = None
        self.screen_size = None

    def setup_driver(self):
        raise NotImplementedError

    def tap_coordinates(self, x, y):
        raise NotImplementedError

    def drag(self, startX, startY, endX, endY):
        raise NotImplementedError

    def swipe(self, direction):
        raise NotImplementedError

    def scroll(self, direction):
        raise NotImplementedError

    def type_text(self, text):
        raise NotImplementedError

    def sleep(self, duration):
        time.sleep(duration)

    def execute(self, script):
        screenshot = self.driver.get_screenshot_as_base64()
        PIL_image = Image.open(BytesIO(base64.b64decode(screenshot)))
        longer_side = max(PIL_image.size)
        aspect_ratio = PIL_image.size[0] / PIL_image.size[1]
        new_size = (960, int(960 / aspect_ratio)) if PIL_image.size[0] == longer_side else (int(960 * aspect_ratio), 960)
        PIL_image = PIL_image.resize(new_size)
        buffered = BytesIO()
        PIL_image.save(buffered, format="PNG")
        screenshot = base64.b64encode(buffered.getvalue()).decode("utf-8")
        payload = {"action": script, "screen_size": self.screen_size, "screenshot": screenshot}
        response = requests.post("https://api.camelqa.com/v1/execute", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        print(response.text)
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

class AndroidClient(BaseClient):
    def __init__(self, api_key, driver=None):
        super().__init__(api_key)
        self.platform = "Android"
        if driver:
            self.driver = driver
        else:
            for _ in range(3):
                try:
                    self.setup_driver()
                    break
                except:
                    pass
            else:
                raise Exception("Failed to setup the driver.")
        self.screen_size = self.driver.get_window_size()

    def setup_driver(self):
        caps = {'deviceName': 'Android Device', 'automationName': 'UiAutomator2', 'autoGrantPermissions': True,
                'newCommandTimeout': 600, 'mjpegScreenshotUrl': "http://localhost:4723/stream.mjpeg"}
        options = UiAutomator2Options().load_capabilities(caps)
        self.driver = webdriver.Remote('http://localhost:4723', options=options)
        self.driver.start_recording_screen()
        self.driver.update_settings({'waitForIdleTimeout': 0, 'shouldWaitForQuiescence': False, 'maxTypingFrequency': 60})
        # get screenshot to test if the driver is working
        self.driver.get_screenshot_as_base64()

    def tap_coordinates(self, x, y):
        self.driver.tap([(x, y)], 1)

    def drag(self, startX, startY, endX, endY):
        self.driver.swipe(startX, startY, endX, endY, 1)

    def swipe(self, direction):
        left = self.window_size["width"] * 0.2
        top = self.window_size["height"] * 0.2
        width = self.window_size["width"] * 0.6
        height = self.window_size["height"] * 0.6
        self.driver.execute_script("mobile: swipeGesture", {"left": left, "top": top, "width": width, "height": height, "direction": direction, "percent": 1.0})

    def scroll(self, direction):
        direction_map = {"up": "down", "down": "up", "left": "right", "right": "left"}
        self.swipe(direction_map[direction])

    def type_text(self, text):
        subprocess.run(["adb", "shell", "input", "text", f"'{text}'"])

class IOSClient(BaseClient):
    def __init__(self, api_key, driver=None, ios_udid=None):
        super().__init__(api_key)
        self.platform = "iOS"
        if driver:
            self.driver = driver
        else:
            # try 3 times to setup the driver
            for _ in range(3):
                try:
                    self.setup_driver(ios_udid)
                    break
                except:
                    pass
            else:
                raise Exception("Failed to setup the driver.")
        self.screen_size = self.driver.get_window_size()

    def setup_driver(self, udid):
        options = XCUITestOptions()
        options.udid = udid
        custom_caps = {"mjpegScreenshotUrl": "http://localhost:9100"}
        options.load_capabilities(custom_caps)
        try:
            self.driver = webdriver.Remote('http://localhost:4723', options=options)
        except:
            self.driver = webdriver.Remote('http://localhost:4723/wd/hub', options=options)
        self.driver.start_recording_screen(forceRestart=True)
        self.driver.update_settings({'waitForIdleTimeout': 0, 'shouldWaitForQuiescence': False, 'maxTypingFrequency': 60})
        # get screenshot to test if the driver is working
        self.driver.get_screenshot_as_base64()

    def tap_coordinates(self, x, y):
        self.driver.execute_script("mobile: tap", {"x": x, "y": y})

    def drag(self, startX, startY, endX, endY):
        self.driver.execute_script("mobile: dragFromToForDuration", {"fromX": startX, "fromY": startY, "toX": endX, "toY": endY, "duration": 1})

    def swipe(self, direction):
        self.driver.execute_script("mobile: swipe", {"direction": direction})

    def scroll(self, direction):
        direction_map = {"up": "down", "down": "up", "left": "right", "right": "left"}
        self.driver.execute_script("mobile: swipe", {"direction": direction_map[direction]})

    def type_text(self, text):
        self.driver.find_element(AppiumBy.IOS_PREDICATE, "type == 'XCUIElementTypeApplication'").send_keys(text)

def Client(api_key, driver=None):
    def get_ios_udid():
        system_profiler_output = subprocess.run(["system_profiler", "SPUSBDataType"], capture_output=True, text=True).stdout
        serial_numbers = re.findall(r'(iPhone|iPad).*?Serial Number: *([^\n]+)', system_profiler_output, re.DOTALL)

        if serial_numbers:
            first_serial_number = serial_numbers[0][1].strip()
            modified_serial_number = first_serial_number[:8] + '-' + first_serial_number[8:]
            return modified_serial_number

    def get_connected_android_devices():
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = result.stdout.splitlines()[1:]  # Skip the first line, which is a header
            connected_devices = [line.split('\t')[0] for line in devices if "device" in line]
            return connected_devices
        except:
            return []

    if driver is not None:
            platform_name = driver.desired_capabilities.get('platformName', '').lower()
            if platform_name == 'android':
                print("Using the provided Appium driver for Android.")
                return AndroidClient(api_key, driver=driver)
            elif platform_name == 'ios':
                print("Using the provided Appium driver for iOS.")
                return IOSClient(api_key, driver=driver)
            else:
                raise Exception("Unsupported platform specified in the provided driver's capabilities.")

    android_devices = get_connected_android_devices()
    if android_devices:
        return AndroidClient(api_key)

    ios_udid = get_ios_udid()
    if ios_udid:
        return IOSClient(api_key, ios_udid=ios_udid)

    raise Exception("No connected devices found or driver provided.")

