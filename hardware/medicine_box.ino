// ESP32 Medicine Box snippet - Posts to ElderCare Bridge Server
// REPLACE WITH YOUR ACTUAL SENSOR/SERVO AND WIFI CODE

#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// VERY IMPORTANT: Change this to the IP address of the PC running backend/app.py
const char* serverUrl = "http://10.19.129.158:5000/api/medicine"; 

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void loop() {
  // 1. READ YOUR MEDICINE BOX STATE HERE
  bool isLidOpen = false; // Replace with reed switch / IR sensor reading
  bool reminderRinging = false; // Replace with logic if it's currently beeping

  // 2. SEND TO DASHBOARD
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    String payload = "{\"lid_open\": " + String(isLidOpen ? "true" : "false") + 
                     ", \"reminder_triggered\": " + String(reminderRinging ? "true" : "false") + "}";
    
    int httpResponseCode = http.POST(payload);
    
    if (httpResponseCode > 0) {
      Serial.print("Medbox state sent, Response: ");
      Serial.println(httpResponseCode);
    } else {
      Serial.print("Error sending POST: ");
      Serial.println(httpResponseCode);
    }
    http.end();
  }

  // Send every 2 seconds matching the dashboard throttling
  delay(2000); 
}
