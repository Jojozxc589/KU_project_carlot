import network
import urequests as requests
import ujson as json
import time
import utime
import machine

ssid = 'JO'
password = 'pun101062'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

def wait_for_connection():
    while not wlan.isconnected():
        print("Connecting to WiFi...")
        time.sleep(1)
    print("Connected to WiFi")
    print(wlan.ifconfig())

wait_for_connection()

def get_distance(trigger_pin, echo_pin):
    trigger = machine.Pin(trigger_pin, machine.Pin.OUT)
    echo = machine.Pin(echo_pin, machine.Pin.IN)
    
    trigger.low()
    utime.sleep_us(2)
    trigger.high()
    utime.sleep_us(10)
    trigger.low()
    
    while echo.value() == 0:
        signal_off = utime.ticks_us()
    while echo.value() == 1:
        signal_on = utime.ticks_us()
    
    time_passed = signal_on - signal_off
    distance = (222 - (time_passed * 0.0343) / 2)
    
    if distance < 0 or distance > 400:
        return None
    return distance

# ตั้งค่า GPIO สำหรับ LED
led_pin = 2  # ใช้ GPIO 2 สำหรับไฟ LED
led = machine.Pin(led_pin, machine.Pin.OUT)

trigger_pin = 4
echo_pin = 5
button_pin = 0  # ขาที่เชื่อมต่อกับปุ่ม

button = machine.Pin(button_pin, machine.Pin.IN, machine.Pin.PULL_UP)

server_url = "http://172.20.10.2:8000/data"

def send_data(data):
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(server_url, data=json.dumps(data), headers=headers)
        if response.status_code == 200:
            print("Data sent successfully")
        else:
            print(f"Failed to send data. Status code: {response.status_code}")
            print("Response text:", response.text)
    except Exception as e:
        print(f"Error sending data: {str(e)}")
    finally:
        response.close() if 'response' in locals() else None

def retry_send_data(data, retries=3):
    for attempt in range(retries):
        if wlan.isconnected():
            try:
                send_data(data)
                break
            except OSError as e:
                print(f"OS Error on attempt {attempt + 1}: {str(e)}")
                print("Retrying to send data...")
                time.sleep(2)
            except Exception as e:
                print(f"Error on attempt {attempt + 1}: {str(e)}")
                time.sleep(2)
        else:
            print("WiFi not connected. Retrying...")
            wlan.connect(ssid, password)
            wait_for_connection()
            time.sleep(1)
    else:
        print("Failed to connect to WiFi after several attempts.")

def save_card_id(card_id):
    with open("card_id.txt", "w") as f:
        f.write(str(card_id))

def load_card_id():
    try:
        with open("card_id.txt", "r") as f:
            card_id = int(f.read())
    except (OSError, ValueError):
        card_id = 1  
    return card_id

card_id = load_card_id()

# ฟังก์ชันคำนวณค่าเฉลี่ยโดยตัดค่าสูงสุดและต่ำสุดออก
def calculate_filtered_average(distances):
    if len(distances) < 3:
        return None  # ต้องมีข้อมูลมากกว่า 3 ค่าเพื่อคำนวณ
    distances.sort()
    filtered_distances = distances[1:-1]  # ตัดค่าสูงสุดและต่ำสุด
    average_distance = sum(filtered_distances) / len(filtered_distances)
    return average_distance

def run_once():
    global card_id  
    last_state = button.value()  

    print("Waiting for button press to start...")
    while True:
        current_state = button.value()
        
        if last_state == 1 and current_state == 0:
            print("Button pressed. Starting measurement...")
            distances = []

            for _ in range(5):
                distance = get_distance(trigger_pin, echo_pin)
                if distance is not None:
                    distances.append(distance)
                print(f"Distance reading {_+1}: {distance:.2f} cm" if distance is not None else "Invalid distance reading")
                time.sleep(0.1)

            average_distance = calculate_filtered_average(distances)
            if average_distance is not None:
                print(f"Filtered average distance for card_id {card_id}: {average_distance:.2f} cm")

                if average_distance > 190:
                    led.on()
                    print("LED ON: Distance is greater than 190 cm")
                else:
                    led.off()
                    print("LED OFF: Distance is less than or equal to 190 cm")

                data_to_send = {
                    "id": card_id,  
                    "distance": average_distance,
                    "license_plate": "",  
                    "card_id": card_id  
                }

                retry_send_data(data_to_send)

                card_id += 1  
                save_card_id(card_id)

                print(f"Done. Waiting for next button press... Next card_id will be {card_id}.")
            else:
                print("No valid distance readings found. Data not sent.")
            
            time.sleep(0.5)
            
            break

        last_state = current_state  

while True:
    run_once()
