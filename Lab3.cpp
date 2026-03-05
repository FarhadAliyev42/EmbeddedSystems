#include "SevSeg.h"
#include <Wire.h>
#include <RTClib.h>

// --- 1. SETTINGS AND PINS ---
SevSeg sevseg;
RTC_DS1307 rtc;

const int buttonPin = A0;    
const int feedbackLED = A1; 
const float targetValue = 10.0;    // Target is now 10 seconds
const int windowMs = 500;          // +/- 500ms (1 second total window)
unsigned long startTime = 0;
bool gameRunning = false;

// --- 2. SETUP ---
void setup() {
  byte numDigits = 4;
  byte digitPins[] = {2, 3, 4, 5}; 
  byte segmentPins[] = {6, 7, 8, 9, 10, 11, 12, 13}; 
  byte hardwareConfig = COMMON_CATHODE; 

  sevseg.begin(hardwareConfig, numDigits, digitPins, segmentPins);

  rtc.begin();
  pinMode(buttonPin, INPUT);
  pinMode(feedbackLED, OUTPUT);
}

// --- 3. MAIN GAME LOOP ---
void loop() {
  if (!gameRunning) {
    sevseg.setNumber(0);
    if (digitalRead(buttonPin) == HIGH) {
      startGame();
      delay(300); // Small debounce to prevent instant trigger
    }
  } else {
    unsigned long elapsed = millis() - startTime;
    float displayTime = elapsed / 1000.0;

    // UPDATE DISPLAY
    sevseg.setNumberF(displayTime, 1);

    // FAILURE CONDITION: 
    // If we pass the end of the window (10.5s) without a click, reset.
    if (elapsed > (targetValue * 10 + windowMs)) { 
      handleFailure(elapsed);
      return; 
    }

    // CHECK FOR USER CLICK
    if (digitalRead(buttonPin) == HIGH) {
      long targetMillis = targetValue * 1000;
      long diff = abs((long)elapsed - targetMillis);

      if (diff <= windowMs) { 
        // SUCCESS: You clicked between 9.5 and 10.5 seconds
        handleSuccess(elapsed);
      } else {
        // MISSED: You clicked too early (before 9.5s)
        handleFailure(elapsed);
      }
    }
  }
  sevseg.refreshDisplay();
}

// --- 4. HELPER FUNCTIONS --- //18.45 --> 18.67 19.1 
void startGame() {
  // Sync with RTC for precision
  DateTime now = rtc.now();
  int currentSec = now.second(); 
  while (rtc.now().second() == currentSec); 

  Serial.print("Game Started! Start Time: ");
  Serial.println(currentSec);
  
  startTime = millis();
  gameRunning = true;
  digitalWrite(feedbackLED, LOW);
}

void handleSuccess(unsigned long finalElapsed) {
  gameRunning = false;
  digitalWrite(feedbackLED, HIGH); 
  
  // Freeze the winning time for 4 seconds
  unsigned long freezeStart = millis();
  while (millis() - freezeStart < 4000) {
    sevseg.setNumberF(finalElapsed / 1000.0, 2); // Show 2 decimals for precision
    sevseg.refreshDisplay();
  }
  digitalWrite(feedbackLED, LOW);
}

void handleFailure(unsigned long finalElapsed) {
  gameRunning = false;
  digitalWrite(feedbackLED, LOW);

  unsigned long freezeStart = millis();

  // Show the stopped time for 1 second
  while (millis() - freezeStart < 1000) {
    sevseg.setNumberF(finalElapsed / 1000.0, 1);
    sevseg.refreshDisplay();
  }
}
