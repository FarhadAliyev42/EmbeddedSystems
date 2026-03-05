/*
 * Lab Task 2: Joystick Direction Controller
 * Dead-zone: 200 to 800
 * X-Axis: Reversed (Left > 800, Right < 200)
 */

// Pin Definitions
const int xPin = A0;
const int yPin = A1;

const int ledUp    = 2;
const int ledDown  = 3;
const int ledLeft  = 4;
const int ledRight = 5;

// Thresholds
const int THRESHOLD_LOW  = 200; 
const int THRESHOLD_HIGH = 800; 

void setup() {
  Serial.begin(115200);

  pinMode(ledUp, OUTPUT);
  pinMode(ledDown, OUTPUT);
  pinMode(ledLeft, OUTPUT);
  pinMode(ledRight, OUTPUT);

  // Optimization: Set ADC Prescaler to 16 for faster sampling
  ADCSRA &= ~(1 << ADPS2);
  ADCSRA |= (1 << ADPS1);
  ADCSRA |= (1 << ADPS0); 
}

// Optimization: Averaging 10 samples for better resolution
int getAverageRead(int pin) {
  long sum = 0;
  for(int i = 0; i < 10; i++) {
    sum += analogRead(pin);
  }
  return sum / 10;
}

void loop() {
  int xVal = getAverageRead(xPin);
  int yVal = getAverageRead(yPin);

  // Reset all LEDs
  digitalWrite(ledUp, LOW);
  digitalWrite(ledDown, LOW);
  digitalWrite(ledLeft, LOW);
  digitalWrite(ledRight, LOW);

  // Y-Axis Logic (Up/Down) - Remains Standard
  if (yVal > THRESHOLD_HIGH) {
    digitalWrite(ledUp, HIGH);
    Serial.println("Direction: UP");
  } 
  else if (yVal < THRESHOLD_LOW) {
    digitalWrite(ledDown, HIGH);
    Serial.println("Direction: DOWN");
  }

  // X-Axis Logic (Left/Right) - REVERSED
  if (xVal > THRESHOLD_HIGH) {
    digitalWrite(ledLeft, HIGH); // Changed from Right to Left
    Serial.print("X-Val: "); Serial.print(xVal);
    Serial.println(" -> Direction: LEFT (Reversed)");
  } 
  else if (xVal < THRESHOLD_LOW) {
    digitalWrite(ledRight, HIGH); // Changed from Left to Right
    Serial.print("X-Val: "); Serial.print(xVal);
    Serial.println(" -> Direction: RIGHT (Reversed)");
  }

  delay(10); 
}
