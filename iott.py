import network
import time
import machine
from umqtt.simple import MQTTClient

# WiFi and MQTT configuration
WIFI_SSID = "Nomad-Fi"
WIFI_PASSWORD = "1234567890"

MQTT_BROKER = "192.168.137.114"
MQTT_PORT = 1883
MQTT_TOPIC = b"fastapi/topic/#"  # wildcard for all subtopics

MQTT_USER = None
MQTT_PASSWORD = None

# Hardware setup
ir_sensor = machine.Pin(15, machine.Pin.IN)  # IR sensor: 1=open, 0=closed
red_led = machine.Pin(2, machine.Pin.OUT)
green_led = machine.Pin(4, machine.Pin.OUT)  # Added green LED

# State flags
door_has_valid_access = False  # Tracks if current access is authorized
alarm_triggered = False
mqtt_client = None

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    timeout = 10
    while timeout > 0:
        if wlan.isconnected():
            print("✅ Connected to WiFi:", wlan.ifconfig())
            return
        print("⌛ Waiting for connection...")
        timeout -= 1
        time.sleep(1)
    
    raise RuntimeError("❌ WiFi connection failed.")

def send_custom_mqtt_message(payload):
    try:
        if mqtt_client:
            mqtt_client.publish(b"fastapi/topic", payload)
            print("📤 MQTT message sent:", payload)
        else:
            print("❗ MQTT client not connected")
    except Exception as e:
        print("❗ MQTT publish error:", e)

def mqtt_callback(topic, msg):
    global door_has_valid_access
    print("\n📨 MQTT callback triggered")
    print("Topic:", topic)
    print("Payload:", msg)

    try:
        payload = msg.decode("utf-8")
        parts = payload.split("/")

        if len(parts) >= 2:
            command = parts[0].strip()
            
            if command == "access":
                lock_id = parts[1].strip()
                user_id = parts[2].strip()
                print("✅ Access granted for user:", user_id)
                door_has_valid_access = True
                red_led.value(0)
                green_led.value(1)  # Green ON = authorized
                send_custom_mqtt_message(f"access_granted/{user_id}/roomX/{lock_id}")

            elif command == "noaccess":
                user_id = parts[2].strip() if len(parts) > 2 else "unknown"
                print("🚫 Access denied for user:", user_id)
                red_led.value(1)
                green_led.value(0)  # Green OFF = denied

            elif command == "intrusion":
                print("🚨 Intrusion Alert:", parts[1])
                red_led.value(1)
                green_led.value(0)

            elif command == "status":
                print("📊 Status check received")
                send_custom_mqtt_message("status_response/device_alive")

            elif command == "reset":
                print("♻️ Resetting flags")
                red_led.value(0)
                green_led.value(0)
                door_has_valid_access = False
                alarm_triggered = False
                send_custom_mqtt_message("reset_acknowledged")

            else:
                print("❓ Unknown command:", command)
        else:
            print("⚠️ Invalid MQTT message format")
    except Exception as e:
        print("❗ MQTT callback error:", e)

def subscribe_mqtt():
    global mqtt_client
    try:
        client_id = "esp32micro"
        if MQTT_USER and MQTT_PASSWORD:
            mqtt_client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT,
                                     user=MQTT_USER, password=MQTT_PASSWORD)
        else:
            mqtt_client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT)

        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(MQTT_TOPIC)
        print("📡 Subscribed to topic:", MQTT_TOPIC)
    except Exception as e:
        print("❗ MQTT connection error:", e)

def trigger_alarm():
    global alarm_triggered
    print("🔔 Triggering Alarm!")
    blink_duration = 5  # 5 seconds total
    end_time = time.time() + blink_duration
    while time.time() < end_time:
        red_led.value(1)
        time.sleep(0.5)  # 0.5s on
        red_led.value(0)
        time.sleep(0.5)  # 0.5s off
    alarm_triggered = True
    send_custom_mqtt_message("intrusion/door_opened_without_permission")

def check_door_state():
    global door_has_valid_access, alarm_triggered
    door_open = ir_sensor.value() == 1  # 1 = open, 0 = closed

    if door_open and not door_has_valid_access and not alarm_triggered:
        print("🚪 Door opened without permission!")
        trigger_alarm()

    elif not door_open:  # Door closed
        if door_has_valid_access:
            print("✅ Door closed after valid access.")
        else:
            print("🔄 Door closed (no valid access).")
        
        # Reset flags when door closes
        door_has_valid_access = False
        alarm_triggered = False
        red_led.value(0)
        green_led.value(0)

# --- Main Execution ---
connect_wifi()
subscribe_mqtt()

# Initialize LEDs
red_led.value(0)
green_led.value(0)

print("🚀 System Ready - Monitoring Door Access")

while True:
    try:
        mqtt_client.check_msg()  # Check for MQTT messages
        check_door_state()       # Monitor door sensor
        time.sleep(0.1)          # Small delay to reduce CPU usage
    except Exception as e:
        print("❗ Main loop error:", e)
        time.sleep(2)