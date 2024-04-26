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
import os

class QAMLExecException(Exception):
    pass

class BaseClient:
    def __init__(self, api_key, api_base_url="https://api.camelqa.com"):
        self.api_key = api_key or os.environ.get("QAML_API_KEY")
        self.api_base_url = os.environ.get("QAML_API_BASE_URL", api_base_url)
        self.driver = None
        self.platform = None
        self.screen_size = None
        self.req_session = requests.Session()
        self.req_session.headers.update({"Authorization": f"Bearer {api_key}"})
        self.system_prompt = None
        self.available_functions = {
            "tap": self.tap_coordinates,
            "drag": self.drag,
            "swipe": self.swipe,
            "scroll": self.scroll,
            "type_text": self.type_text,
            "sleep": self.sleep,
            "report_error": self.report_error
        }

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

    def report_error(self, reason):
        raise QAMLExecException(reason)

    def get_screenshot(self):
        screenshot = self.driver.get_screenshot_as_base64()
        PIL_image = Image.open(BytesIO(base64.b64decode(screenshot)))
        longer_side = max(PIL_image.size)
        aspect_ratio = PIL_image.size[0] / PIL_image.size[1]
        new_size = (960, int(960 / aspect_ratio)) if PIL_image.size[0] == longer_side else (int(960 * aspect_ratio), 960)
        PIL_image = PIL_image.resize(new_size)
        buffered = BytesIO()
        PIL_image.save(buffered, format="PNG")
        screenshot = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return screenshot

    def _execute_function(self, function_name, **kwargs):
        function = self.available_functions.get(function_name)
        if function:
            function(**kwargs)

    def execute(self, script):
        screenshot = self.get_screenshot()
        """
        now = time.time()
        appium_page_source = self.driver.page_source
        print(f"Page source: {appium_page_source}", time.time() - now)
        """
        payload = {"action": script, "screen_size": self.screen_size, "screenshot": screenshot, "platform": self.platform, "extra_context": self.system_prompt}
        response = self.req_session.post(f"{self.api_base_url}/v1/execute", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        print(f"Action: {script} - Response: {response.text}")
        try:
            actions = response.json()
            for action in actions:
                self._execute_function(action["name"], **json.loads(action["arguments"]))
        except Exception as e:
            print(e)
            pass

    def assert_condition(self, script):
        screenshot = self.get_screenshot()
        payload = {"assertion": script, "screen_size": self.screen_size, "screenshot": screenshot, "platform": self.platform, "extra_context": self.system_prompt}
        response = self.req_session.post(f"{self.api_base_url}/v1/assert", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        print(f"Action: {script} - Response: {response.text}")
        assertion = response.json()[0]
        args = json.loads(assertion["arguments"])
        if not args["result"]:
            raise QAMLExecException(f"Assertion failed: {script}. Reason: {args['reason']}")
        return response.json()

    def agent(self, task):
        progress = []
        while True:
            screenshot = self.get_screenshot()
            payload = {"task": task, "progress": progress, "platform": self.platform, "screenshot": screenshot}
            response = self.req_session.post(f"{self.api_base_url}/v1/agent", json=payload)
            response_json = response.json()
            status = response_json["status"]
            progress += response_json["progress"]
            actions = response_json["actions"]
            if status != "in_progress":
                return status, progress
            for action in actions:
                self.execute(action)

class AndroidClient(BaseClient):
    def __init__(self, api_key, driver=None):
        super().__init__(api_key)
        self.platform = "Android"
        if driver:
            self.driver = driver
        else:
            max_retry = 3
            for i in range(max_retry):
                try:
                    self.setup_driver()
                    break
                except Exception as e:
                    if i == max_retry - 1:
                        raise e
        self.screen_size = self.driver.get_window_size()

    def setup_driver(self):
        caps = {'deviceName': 'Android Device', 'automationName': 'UiAutomator2', 'autoGrantPermissions': True,
                'newCommandTimeout': 600, 'mjpegScreenshotUrl': "http://localhost:4723/stream.mjpeg"}
        options = UiAutomator2Options().load_capabilities(caps)

        def create_driver(options):
            try:
                return webdriver.Remote('http://localhost:4723', options=options)
            except:
                return webdriver.Remote('http://localhost:4723/wd/hub', options=options)
        try:
            self.driver = webdriver.Remote('http://localhost:4723', options=options)
        except:
            # Try again without mjpeg-consumer dependency
            caps.pop('mjpegScreenshotUrl')
            options = UiAutomator2Options().load_capabilities(caps)
            self.driver = create_driver(options)

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
    def __init__(self, api_key, driver=None, use_mjpeg=True, use_hid_typing=False):
        super().__init__(api_key)
        self.available_functions["switch_to_app"] = self.switch_to_app
        self.platform = "iOS"
        self.use_mjpeg = use_mjpeg
        self.use_hid_typing = use_hid_typing
        if driver:
            self.driver = driver
        else:
            def get_ios_udid():
                system_profiler_output = subprocess.run(["system_profiler", "SPUSBDataType"], capture_output=True, text=True).stdout
                serial_numbers = re.findall(r'(iPhone|iPad).*?Serial Number: *([^\n]+)', system_profiler_output, re.DOTALL)

                if serial_numbers:
                    first_serial_number = serial_numbers[0][1].strip()
                    modified_serial_number = first_serial_number[:8] + '-' + first_serial_number[8:]
                    return modified_serial_number
            ios_udid = get_ios_udid()
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
        if udid:
            options.udid = udid
        options.new_command_timeout = 60 * 5 # 5 minutes
        if self.use_mjpeg:
            custom_caps = {"mjpegScreenshotUrl": "http://localhost:9100"}
            options.load_capabilities(custom_caps)

        def create_driver(options):
            try:
                return webdriver.Remote('http://localhost:4723', options=options)
            except:
                return webdriver.Remote('http://localhost:4723/wd/hub', options=options)
        try:
            self.driver = create_driver(options)
        except:
            # Try again without mjpeg-consumer dependency
            options = XCUITestOptions()
            options.udid = udid
            self.driver = create_driver(options)

        if self.use_mjpeg:
            print("Using MJPEG screenshot.")
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
        if self.use_hid_typing:
            self.type_text_hid(text)
        else:
            try:
                self.driver.find_element(AppiumBy.IOS_PREDICATE, "type == 'XCUIElementTypeApplication'").send_keys(text)
            except:
                self.type_text_hid(text)

    def type_text_hid(self, text):
        special_chars = {
                ' ': 0x2C, '!': 0x1E, '@': 0x1F, '#': 0x20, '$': 0x21, '%': 0x22,
                '^': 0x23, '&': 0x24, '*': 0x25, '(': 0x26, ')': 0x27, '-': 0x2D,
                '_': 0x2D, '=': 0x2E, '+': 0x2E, '[': 0x2F, '{': 0x2F, ']': 0x30,
                '}': 0x30, '\\': 0x31, '|': 0x31, ';': 0x33, ':': 0x33, '\'': 0x34,
                '"': 0x34, '`': 0x35, '~': 0x35, ',': 0x36, '<': 0x36, '.': 0x37,
                '>': 0x37, '/': 0x38, '?': 0x38
                }

        # Base HID usage codes
        hid_base_lower = 0x04  # HID usage for 'a'
        hid_base_upper = 0x04  # HID usage for 'A'
        hid_base_number = 0x1E  # HID usage for '1'

        for char in text:
            usage = None
            shift = False

            if 'a' <= char <= 'z':
                usage = hid_base_lower + (ord(char) - ord('a'))
            elif 'A' <= char <= 'Z':
                usage = hid_base_upper + (ord(char) - ord('A'))
                shift = True
            elif '1' <= char <= '9':
                usage = hid_base_number + (ord(char) - ord('1'))
            elif char == '0':
                usage = 0x27
            elif char in special_chars:
                usage = special_chars[char]
                # Determine if shift needs to be pressed for special characters
                shift = char in '~!@#$%^&*()_+{}|:"<>?'

            if usage is None:
                continue

            self.driver.execute_script("mobile: performIoHidEvent", {"page": 0x07, "usage": usage, "durationSeconds": 0.005})  # Key down
            self.driver.execute_script("mobile: performIoHidEvent", {"page": 0x07, "usage": 0x00, "durationSeconds": 0.005})  # Key up

    def switch_to_app(self, bundle_id):
        self.driver.activate_app(bundle_id)

def Client(api_key, driver=None, use_mjpeg=True, use_hid_typing=False):

    def get_connected_android_devices():
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            devices = result.stdout.splitlines()[1:]  # Skip the first line, which is a header
            connected_devices = [line.split('\t')[0] for line in devices if "device" in line]
            return connected_devices
        except:
            return []

    if driver is not None:
        platform_name = driver.capabilities.get("platformName").lower()
        if platform_name == 'android':
            print("Using the provided Appium driver for Android.")
            return AndroidClient(api_key, driver=driver)
        elif platform_name == 'ios':
            print("Using the provided Appium driver for iOS.")
            return IOSClient(api_key, driver=driver, use_hid_typing=use_hid_typing)
        else:
            raise Exception("Unsupported platform specified in the provided driver's capabilities.")

    android_devices = get_connected_android_devices()
    if android_devices:
        return AndroidClient(api_key)

    try:
        return IOSClient(api_key, use_mjpeg=use_mjpeg, use_hid_typing=use_hid_typing)
    except:
        raise Exception("No connected devices found or driver provided.")

