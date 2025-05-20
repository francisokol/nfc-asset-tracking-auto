from smartcard.System import readers
import requests
import time



RAILWAY_URL = "https://nfc-based-asset-tracking-system.up.railway.app"

def main(): 
    r = readers()
    if not r:
        print("❌ No NFC reader found. Make sure the driver is installed.")
        exit()

    reader = r[0].createConnection()
    last_scanned = None
    last_scan_time = 0
    SCAN_COOLDOWN = 5  #5 seconds between scans

    print(f"🌐 Connected to server at {RAILWAY_URL}")
    print("📡 NFC Reader initialized successfully")
    print("ℹ️ Waiting for tags to scan...")
    
    while True:
        try:
            # Try to connect to a card
            try:
                reader.connect()
                command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                response, sw1, sw2 = reader.transmit(command)
            except Exception as e:
                # If no card is present, reset last_scanned
                if "Card is not connected" in str(e):
                    last_scanned = None
                    time.sleep(1)
                    continue
                raise e

            if sw1 == 0x90:
                nfc_id = ''.join('{:02X}'.format(x) for x in response)
                current_time = time.time()
                
                # Only process if it's a new tag or enough time has passed
                if nfc_id != last_scanned or (current_time - last_scan_time) > SCAN_COOLDOWN:
                    print("\n✅ New NFC tag detected!")
                    print(f"📎 Tag ID: {nfc_id}")
                    try:
                        # First try auto-scan to see if tag is registered
                        print("\n📤 Checking tag status...")
                        response = requests.post(
                            f"{RAILWAY_URL}/admin/auto-scan",
                            json={"nfc_id": nfc_id}
                        )
                        result = response.json()

                        # Update last_scanned regardless of registration status
                        last_scanned = nfc_id
                        last_scan_time = current_time

                        # If tag is not registered, send to registration endpoint
                        if result.get('status') == 'error' and 'not registered' in result.get('message', '').lower():
                            print("\n📝 Tag not registered, sending to registration...")
                            reg_response = requests.post(
                                f"{RAILWAY_URL}/admin/nfc-update",
                                json={"nfc_id": nfc_id}
                            )
                            print(f"📥 Registration Response: {reg_response.status_code}")
                            print(f"📄 Content: {reg_response.text}")
                        else:
                            # For registered tags, show the auto-scan result
                            if result.get('status') == 'success':
                                print(f"\n✨ Success: {result.get('message')}")
                                # Add a forced delay after successful scan
                                time.sleep(2)
                            else:
                                print(f"\n⚠️ Notice: {result.get('message')}")

                    except requests.exceptions.RequestException as e:
                        print(f"\n⛔ Network Error: {str(e)}")
                        print("🔄 Will retry on next scan...")

        except Exception as e:
            if "Card is not connected" not in str(e):  # Suppress common disconnect message
                print(f"\n⛔ Error: {str(e)}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 NFC Reader stopped by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {str(e)}")
