#include <Arduino.h>
#include <LiquidCrystal.h>

// --- Pin Definitions ---
const int contrastPin = 6;      
const int rs = 7, en = 8, d4 = 9, d5 = 10, d6 = 11, d7 = 12; 
const int soundAnalogPin = A0;  
const int interruptPin = 2;     // Digital pin 2 for Hardware Interrupt
const int ledPin = 13;          

LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

// --- Non-Blocking Variables ---
unsigned long previousMillis = 0;   
const long updateInterval = 50;  

unsigned long ledTriggeredMillis = 0; 
const long ledOnDuration = 500;       

// Volatile flag for the interrupt
volatile bool soundSpikeDetected = false; 

// --- Interrupt Service Routine ---
void triggerLED() {
  soundSpikeDetected = true; 
}

void setup() {
  Serial.begin(115200);

  pinMode(ledPin, OUTPUT);
  pinMode(contrastPin, OUTPUT);
  pinMode(interruptPin, INPUT);

  lcd.begin(16, 2);
  lcd.clear();          // Wipes any random garbage currently in the LCD's memory
  lcd.setCursor(0, 0);  // Start at the top-left

  attachInterrupt(digitalPinToInterrupt(interruptPin), triggerLED, RISING);
}

void loop() {
  unsigned long currentMillis = millis();
  int interruptOccurred = 0; // Flag to send to Python

  // 1. Handle the Interrupt Event 
  if (soundSpikeDetected) {
    digitalWrite(ledPin, HIGH);        
    ledTriggeredMillis = currentMillis; 
    soundSpikeDetected = false;        
    interruptOccurred = 1; //a spike happened
  }

  // Turn off LED after duration
  if (digitalRead(ledPin) == HIGH && (currentMillis - ledTriggeredMillis >= ledOnDuration)) {
    digitalWrite(ledPin, LOW); 
  } 

  // 2. LCD and UART Updates (Non-Blocking)
  if (currentMillis - previousMillis >= updateInterval) {
    previousMillis = currentMillis; 
    
    int soundLevel = analogRead(soundAnalogPin);

    // Update LCD
    lcd.setCursor(0, 1);       // Move to the bottom-left
    lcd.print("Val: ");        
    lcd.print(soundLevel);     
    lcd.print("          ");   // Print 10 blank spaces

    // Send data over UART for your Python GUI
    Serial.print(soundLevel);
    Serial.print(",");
    Serial.println(interruptOccurred);
  }
}
