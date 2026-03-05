#include <Arduino.h>

// Joystick Pins
const int pinX = A0;
const int pinY = A1;
const int pinSW = 2;

// LED Pins
const int LED_RIGHT = 8;
const int LED_LEFT = 9;
const int LED_UP = 10;
const int LED_DOWN = 11;

void setup() {
  pinMode(LED_RIGHT, OUTPUT);
  pinMode(LED_LEFT, OUTPUT);
  pinMode(LED_UP, OUTPUT);
  pinMode(LED_DOWN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int xVal = analogRead(pinX);
  int yVal = analogRead(pinY);
  int swVal = digitalRead(pinSW);
  
  float voltX = (xVal * 5.0) / 1023.0;
  float voltY = (yVal * 5.0) / 1023.0;

  bool r = (voltX < 1.0); 
  bool l = (voltX > 4.0); 
  bool u = (voltY > 4.0); 
  bool d = (voltY < 1.0); 

  digitalWrite(LED_RIGHT, r);
  digitalWrite(LED_LEFT, l);
  digitalWrite(LED_UP, u);
  digitalWrite(LED_DOWN, d);

  // Telemetry Format: X:v,Y:v,B:s,R:0/1,L:0/1,U:0/1,D:0/1
  Serial.print("X:"); Serial.print(voltX, 2);
  Serial.print(",Y:"); Serial.print(voltY, 2);
  Serial.print(",B:"); Serial.print(swVal == LOW ? "PRSD" : "RLSD");
  Serial.print(",R:"); Serial.print(r);
  Serial.print(",L:"); Serial.print(l);
  Serial.print(",U:"); Serial.print(u);
  Serial.print(",D:"); Serial.println(d);

  delay(40); 
}
