// ============================================================
//  Lab Task 7 — Multi-component Security System
//  Arduino UNO  |  Keypad + IR remote + RFID RC522 + 2 LEDs
// ============================================================
//  Libraries required (install via Arduino Library Manager):
//    Keypad       by Mark Stanley / Alexander Brevig
//    IRremote     by shirriff / z3t0 / ArminJo
//    MFRC522      by GithubCommunity
// ============================================================

#include <Keypad.h>
#include <IRremote.hpp>       // IRremote v3+
#include <SPI.h>
#include <MFRC522.h>

// ── Pin definitions ──────────────────────────────────────────
// Keypad
const byte ROWS = 4, COLS = 4;
byte rowPins[ROWS] = {2, 3, 4, 5};
byte colPins[COLS]  = {6, 7, 8, 9};

// RFID
#define SS_PIN   10
#define RST_PIN  255          // RST hardwired to 5V — no pin needed

// IR receiver
#define IR_PIN   A0           // A0 used as digital input

// LEDs
#define LED_A    A1           // State indicator LED A
#define LED_B    A2           // State indicator LED B

// ── Keypad layout ────────────────────────────────────────────
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);

// ── RFID ─────────────────────────────────────────────────────
MFRC522 mfrc522(SS_PIN, RST_PIN);

// ── System state ─────────────────────────────────────────────
enum State { WAITING, LOCKED, UNLOCKED };
State systemState = WAITING;

// ── Code storage ─────────────────────────────────────────────
String setCode    = "";       // code entered via keypad to lock
String enteredCode = "";      // code being built digit by digit
String irCode     = "";       // code being built via IR remote

// ── Timing ───────────────────────────────────────────────────
unsigned long lastBlink = 0;
bool blinkOn = false;

// ── IR command bytes for digits 0-9 ──────────────────────────
// In NEC protocol the raw 32-bit value is:
//   [addr inverted][addr][cmd inverted][cmd]  (LSB first)
// We extract just the command byte (bits 8-15 of raw value).
// This works regardless of which Elegoo remote variant you have.
// Your remote's command bytes detected from serial output:
const uint8_t IR_CMD[10] = {
  0x19,   // 0  — not yet confirmed, press 0 after upload to verify
  0x0C,   // 1  ← confirmed (F30CFF00)
  0x18,   // 2  ← confirmed (E718FF00)
  0x5E,   // 3  ← confirmed (A15EFF00)
  0x08,   // 4  ← confirmed (F708FF00)
  0x5A,   // 5  ← confirmed (A55AFF00)
  0x42,   // 6  ← confirmed (BD42FF00)
  0x52,   // 7  ← confirmed (AD52FF00)
  0x4A,   // 8  ← confirmed (B54AFF00)
  0x19,   // 9  — not yet confirmed, press 9 after upload to verify
};

// ── Forward declarations ──────────────────────────────────────
void updateLEDs();
void handleWaiting();
void handleLocked();
void handleUnlocked();
void flashLEDs(int times, int ms);
char irToDigit(uint32_t raw);
void printTagSerial(byte *uid, byte uidSize);

// ============================================================
void setup() {
  Serial.begin(9600);

  // LED pins
  pinMode(LED_A, OUTPUT);
  pinMode(LED_B, OUTPUT);

  // RFID
  SPI.begin();
  mfrc522.PCD_Init();

  // IR receiver
  IrReceiver.begin(IR_PIN, DISABLE_LED_FEEDBACK);

  Serial.println("SYSTEM_READY");
  Serial.println("Enter 4-digit code on keypad to lock.");
}

// ============================================================
void loop() {
  switch (systemState) {
    case WAITING:   handleWaiting();   break;
    case LOCKED:    handleLocked();    break;
    case UNLOCKED:  handleUnlocked();  break;
  }
  updateLEDs();
}

// ── WAITING state ────────────────────────────────────────────
// User types 4-digit code on keypad → system locks
void handleWaiting() {
  char key = keypad.getKey();
  if (!key) return;

  // Only accept digit keys 0-9
  if (key >= '0' && key <= '9') {
    setCode += key;
    Serial.print("*");          // echo asterisk for privacy

    if (setCode.length() == 4) {
      // Code set — transition to LOCKED
      systemState = LOCKED;
      enteredCode = "";
      irCode = "";
      Serial.println();
      Serial.println("LOCKED");
    }
  }

  // '*' clears partial entry
  if (key == '*') {
    setCode = "";
    Serial.println("\nCleared.");
  }
}

// ── LOCKED state ─────────────────────────────────────────────
// User enters same 4-digit code via IR remote → unlocks
void handleLocked() {
  if (!IrReceiver.decode()) return;

  uint32_t raw = IrReceiver.decodedIRData.decodedRawData;
  IrReceiver.resume();

  // Ignore repeat codes
  if (IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT) return;

  char digit = irToDigit(raw);
  if (digit == 0) return;       // not a digit button

  irCode += digit;
  Serial.print("*");

  if (irCode.length() == 4) {
    Serial.println();
    if (irCode == setCode) {
      systemState = UNLOCKED;
      irCode = "";
      Serial.println("UNLOCKED");
    } else {
      Serial.println("WRONG CODE — try again.");
      irCode = "";
    }
  }
}

// ── UNLOCKED state ───────────────────────────────────────────
// RFID reader active — scans tags and sends UID over serial.
// Press # on keypad to re-lock without resetting Arduino.
void handleUnlocked() {
  // Check # key on keypad to re-lock
  char key = keypad.getKey();
  if (key == '#') {
    systemState = LOCKED;
    irCode = "";
    Serial.println("RE-LOCKED via keypad #");
    return;
  }

  // Check for new RFID card
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial())   return;

  // Flash both LEDs to confirm scan
  flashLEDs(2, 150);

  // Send tag data to PC over serial
  printTagSerial(mfrc522.uid.uidByte, mfrc522.uid.size);

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();

  delay(500);   // debounce — prevent double reads
}

// ── LED patterns ─────────────────────────────────────────────
//  WAITING  : LED_A slow blink (every 800 ms), LED_B off
//  LOCKED   : LED_A solid ON,                  LED_B off
//  UNLOCKED : LED_A off,                        LED_B solid ON
void updateLEDs() {
  switch (systemState) {
    case WAITING:
      if (millis() - lastBlink > 800) {
        lastBlink = millis();
        blinkOn = !blinkOn;
        digitalWrite(LED_A, blinkOn ? HIGH : LOW);
      }
      digitalWrite(LED_B, LOW);
      break;

    case LOCKED:
      digitalWrite(LED_A, HIGH);
      digitalWrite(LED_B, LOW);
      break;

    case UNLOCKED:
      digitalWrite(LED_A, LOW);
      digitalWrite(LED_B, HIGH);
      break;
  }
}

// ── Flash both LEDs (used on RFID scan) ──────────────────────
void flashLEDs(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_A, HIGH);
    digitalWrite(LED_B, HIGH);
    delay(ms);
    digitalWrite(LED_A, LOW);
    digitalWrite(LED_B, LOW);
    delay(ms);
  }
  // Restore correct LED state after flash
  updateLEDs();
}

// ── Map IR raw value to digit character ──────────────────────
// NEC raw value from IRremote v3 is stored as 0x00FF[CMD][ADDR]
// Command byte sits at bits 23-16, so shift right by 16.
char irToDigit(uint32_t raw) {
  uint8_t cmd = (raw >> 16) & 0xFF;
  Serial.print("CMD:0x"); Serial.println(cmd, HEX);  // debug line
  for (int i = 0; i <= 9; i++) {
    if (cmd == IR_CMD[i]) return ('0' + i);
  }
  return 0;   // not a digit button
}

// ── Print UID to Serial in format Python can parse ───────────
//  Format:  TAG:AABBCCDD
void printTagSerial(byte *uid, byte uidSize) {
  Serial.print("TAG:");
  for (byte i = 0; i < uidSize; i++) {
    if (uid[i] < 0x10) Serial.print("0");
    Serial.print(uid[i], HEX); 
  }
  Serial.println();
}
