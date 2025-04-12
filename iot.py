import network
import time
from machine import Pin
from umqtt.simple import MQTTClient

# ===== Hardware Configuration =====
GREEN_LED = Pin(25, Pin.OUT)  # Replace with your actual GPIO pin
RED_LED = Pin(26, Pin.OUT)    # Replace with your actual GPIO pin
IR_SENSOR = Pin(27, Pin.IN)   # Replace with your actual GPIO pin

# ===== WiFi Settings =====
WIFI_SSID = "Makhlouf's Galaxy S20 5G"
WIFI_PASSWORD = "unda7180"

# ===== MQTT Settings =====
MQTT_BROKER = "192.168.168.29"
MQTT_PORT = 1883
MQTT_TOPIC_ACCESS = b"fastapi/access"
MQTT_TOPIC_SECURITY = b"fastapi/security"
MQTT_USER = ""
MQTT_PASSWORD = ""
CLIENT_ID = b"esp32micro"

# ===== System Variables =====
ACCESS_GRANTED = False
DOOR_OPEN = False
ALARM_ACTIVE = False

# ===== Connect to WiFi =====
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
    print("WiFi connected. IP:", wlan.ifconfig()[0])
    return wlan

# ===== MQTT Functions =====
def connect_mqtt():
    try:
        print("Connecting to MQTT broker...")
        client = MQTTClient(CLIENT_ID, MQTT_BROKER, port=MQTT_PORT, user=MQTT_USER, password=MQTT_PASSWORD)
        client.connect()
        print("Connected to MQTT broker.")
        return client
    except Exception as e:
        print("MQTT connection error:", e)
        return None

def send_mqtt_message(client, topic, message):
    try:
        client.publish(topic, message)
        print("MQTT message sent to", topic, ":", message)
    except Exception as e:
        print("Failed to send MQTT message:", e)

# ===== Access Control Functions =====
def grant_access(client):
    global ACCESS_GRANTED
    ACCESS_GRANTED = True
    GREEN_LED.on()
    RED_LED.off()
    send_mqtt_message(client, MQTT_TOPIC_ACCESS, "ACCESS_GRANTED")
    print("Access granted")

def deny_access(client):
    global ACCESS_GRANTED
    ACCESS_GRANTED = False
    GREEN_LED.off()
    RED_LED.on()
    send_mqtt_message(client, MQTT_TOPIC_ACCESS, "ACCESS_DENIED")
    print("Access denied")

def trigger_alarm(client):
    global ALARM_ACTIVE
    ALARM_ACTIVE = True
    print("ALARM TRIGGERED - Unauthorized access!")
    send_mqtt_message(client, MQTT_TOPIC_SECURITY, "UNAUTHORIZED_ACCESS")
    
    # Blink red LED for 10 seconds
    for _ in range(10):
        RED_LED.on()
        time.sleep(0.5)
        RED_LED.off()
        time.sleep(0.5)
    
    ALARM_ACTIVE = False

# ===== Main Loop =====
def main():
    global DOOR_OPEN, ACCESS_GRANTED, ALARM_ACTIVE
    
    # Initialize hardware
    GREEN_LED.off()
    RED_LED.on()
    
    # Connect to network
    connect_wifi()
    mqtt_client = connect_mqtt()
    
    # Simulate access check
    access_counter = 0
    
    while True:
        # Check IR sensor (door status)
        door_status = IR_SENSOR.value()
        
        if door_status and not DOOR_OPEN:
            print("Door opened")
            DOOR_OPEN = True
            
            # Simulate access check
            access_counter += 1
            if access_counter % 2 == 1:  # Every odd attempt granted
                grant_access(mqtt_client)
            else:
                deny_access(mqtt_client)
                
                # Trigger alarm if unauthorized
                if not ACCESS_GRANTED:
                    trigger_alarm(mqtt_client)
                    
        elif not door_status and DOOR_OPEN:
            print("Door closed")
            DOOR_OPEN = False
            ACCESS_GRANTED = False
            GREEN_LED.off()
            RED_LED.off()
        
        # Maintain MQTT connection
        try:
            if mqtt_client:
                mqtt_client.check_msg()
        except Exception as e:
            print("MQTT error:", e)
            mqtt_client = connect_mqtt()
        
        time.sleep(0.1)

if __name__ == "__main__":
    main()