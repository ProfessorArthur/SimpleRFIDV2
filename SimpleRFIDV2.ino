#include <SPI.h>
#include <MFRC522.h>

// RC522 <-> Arduino Uno R3 wiring (SPI):
// - VCC  -> 3.3V (do not use 5V)
// - GND  -> GND
// - RST  -> D9
// - SDA/SS -> D10
// - MOSI -> D11
// - MISO -> D12
// - SCK  -> D13
//
// This sketch uses the MFRC522 library with SPI.

#define SS_PIN 10
#define RST_PIN 9
#define BUZZER_PIN 6

MFRC522 rfid(SS_PIN, RST_PIN);

uint8_t lastUid[10] = {0};
byte lastUidSize = 0;
unsigned long lastScanMs = 0;
const unsigned long RESCAN_GUARD_MS = 1000;

bool sameAsLastUid(const MFRC522::Uid &uid) {
  if (uid.size != lastUidSize) {
    return false;
  }

  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] != lastUid[i]) {
      return false;
    }
  }

  return true;
}

void rememberUid(const MFRC522::Uid &uid) {
  lastUidSize = uid.size;
  for (byte i = 0; i < uid.size && i < sizeof(lastUid); i++) {
    lastUid[i] = uid.uidByte[i];
  }
  lastScanMs = millis();
}

void clearUidGuardIfExpired() {
  if (lastUidSize > 0 && (millis() - lastScanMs) > RESCAN_GUARD_MS) {
    lastUidSize = 0;
  }
}

String uidToHex(const MFRC522::Uid &uid) {
  String out;
  out.reserve(uid.size * 2);

  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 0x10) {
      out += '0';
    }
    out += String(uid.uidByte[i], HEX);
  }

  out.toUpperCase();
  return out;
}

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  tone(BUZZER_PIN, 1200, 100);
  delay(130);
  noTone(BUZZER_PIN);

  Serial.println("RFID serial bridge ready. Scan a tag...");
}

void loop() {
  clearUidGuardIfExpired();

  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }

  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

  if (sameAsLastUid(rfid.uid) && (millis() - lastScanMs) < RESCAN_GUARD_MS) {
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
    return;
  }

  String uidHex = uidToHex(rfid.uid);

  // One UID per line for the desktop Python bridge script.
  Serial.println(uidHex);

  digitalWrite(LED_BUILTIN, HIGH);
  tone(BUZZER_PIN, 1800, 90);
  delay(120);
  noTone(BUZZER_PIN);
  digitalWrite(LED_BUILTIN, LOW);

  rememberUid(rfid.uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}