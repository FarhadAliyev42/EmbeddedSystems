#include <Wire.h> 
#include <Arduino.h> 
#include <LiquidCrystal_I2C.h>

const int soundAnalogPin = A0;
const int soundDigitalPin = 2; 
const int ledPin = 13;

LiquidCrystal_I2C lcd(0x27, 16, 2);

// Non-blocking timing variables
unsigned long previousMillis = 0;
const long updateInterval = 100; 

volatile bool thresholdTriggered = false; 
unsigned long ledTurnOnTime = 0;
const long ledDuration = 500; // Keep LED on for 500ms after a loud noise

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
  pinMode(soundDigitalPin, INPUT);

  lcd.init();
  lcd.backlight();

  attachInterrupt(digitalPinToInterrupt(soundDigitalPin), soundISR, RISING);
}

void loop() {
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis;
    int soundLevel = analogRead(soundAnalogPin);

    lcd.setCursor(0, 0);
    lcd.print("Sound Lvl: ");
    lcd.print(soundLevel);
    lcd.print("    "); 

    // Format: "SoundLevel,ThresholdState" 
    Serial.print(soundLevel);
    Serial.print(",");
    Serial.println(thresholdTriggered ? 1 : 0);
  }

  if (thresholdTriggered) {
    digitalWrite(ledPin, HIGH);
    ledTurnOnTime = currentMillis;
    thresholdTriggered = false; // Reset the flag so it doesn't stay stuck
  }

  // Turn LED off if the duration has passed
  if (digitalRead(ledPin) == HIGH && (currentMillis - ledTurnOnTime >= ledDuration)) {
    digitalWrite(ledPin, LOW);
  }
}

// The Interrupt Service Routine 
void soundISR() {
  thresholdTriggered = true;
}
