#include <Arduino.h>
#include <Servo.h>
#include <Stepper.h>

// ─────────────────────────────────────────────
//  PIN DEFINITIONS
// ─────────────────────────────────────────────
#define BTN1_PIN      10
#define BTN2_PIN       6
#define BUZZER_PIN     7
#define SERVO_PIN      9
#define STEP_IN1       2
#define STEP_IN2       3
#define STEP_IN3       4
#define STEP_IN4       5

#define STEPS_PER_REV  2048
#define STEPPER_RPM    10
#define STEP_PER_WIN   128

Stepper stepper(STEPS_PER_REV, STEP_IN1, STEP_IN3, STEP_IN2, STEP_IN4);
Servo   servo;

#define SERVO_IDLE  90
#define SERVO_P1     0
#define SERVO_P2   180

// ─────────────────────────────────────────────
//  GAME STATE
// ─────────────────────────────────────────────
enum State { ST_IDLE, ST_COUNTDOWN, ST_REACT, ST_RESULT };

State         gameState    = ST_IDLE;
int           p1Wins       = 0;
int           p2Wins       = 0;
int           roundNum     = 0;
int           stepperPos   = 0;
String        p1Name       = "P1";
String        p2Name       = "P2";

// Countdown
int           cdRemain     = 0;
unsigned long cdNextBeep   = 0;

// React
unsigned long buzzAt       = 0;
long          p1RT         = -1;
long          p2RT         = -1;
bool          p1Fired      = false;
bool          p2Fired      = false;
bool          p1WasHigh    = true;
bool          p2WasHigh    = true;

// Result pause
unsigned long resultUntil  = 0;

// ─────────────────────────────────────────────
//  NON-BLOCKING BUZZER
//  Instead of delay() inside a beep, we just
//  record when to turn the buzzer OFF.
// ─────────────────────────────────────────────
unsigned long buzzerOffAt  = 0;   // 0 = not scheduled

void buzzerUpdate() {
  if (buzzerOffAt > 0 && millis() >= buzzerOffAt) {
    digitalWrite(BUZZER_PIN, LOW);
    buzzerOffAt = 0;
  }
}

// Schedule a beep of given duration — returns immediately, no blocking
void beepAsync(int ms) {
  digitalWrite(BUZZER_PIN, HIGH);
  buzzerOffAt = millis() + ms;
}

// ─────────────────────────────────────────────
//  NON-BLOCKING BUTTON DEBOUNCE
//  We track how long each pin has been
//  continuously LOW. Only confirm a press after
//  DEBOUNCE_MS of uninterrupted LOW.
//  No delay() anywhere — checked every loop.
// ─────────────────────────────────────────────
#define DEBOUNCE_MS  40

struct Btn {
  int           pin;
  bool          wasHigh;      // saw HIGH at least once this phase
  bool          fired;        // reaction already recorded this phase
  bool          pressing;     // currently in a debounce window
  unsigned long lowSince;     // when pin first went LOW this press
};

Btn b1 = { BTN1_PIN, true, false, false, 0 };
Btn b2 = { BTN2_PIN, true, false, false, 0 };

void resetButtons() {
  b1 = { BTN1_PIN, (digitalRead(BTN1_PIN) == HIGH), false, false, 0 };
  b2 = { BTN2_PIN, (digitalRead(BTN2_PIN) == HIGH), false, false, 0 };
}

// Returns true on the single frame a confirmed press is detected.
// Non-blocking — call every loop iteration.
bool updateBtn(Btn &b) {
  bool raw = (digitalRead(b.pin) == LOW);  // LOW = pressed

  if (!raw) {
    // Button released — update wasHigh, reset debounce window
    b.wasHigh  = true;
    b.pressing = false;
    return false;
  }

  // Button is LOW (pressed)
  if (!b.wasHigh) return false;   // not armed yet — ignore

  if (!b.pressing) {
    // Just went LOW — start debounce window
    b.pressing = true;
    b.lowSince = millis();
    return false;
  }

  // Already in debounce window — check if held long enough
  if (!b.fired && millis() - b.lowSince >= DEBOUNCE_MS) {
    b.fired = true;
    return true;    // confirmed press event
  }

  return false;
}

// ─────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────
void powerDownStepper() {
  digitalWrite(STEP_IN1, LOW); digitalWrite(STEP_IN2, LOW);
  digitalWrite(STEP_IN3, LOW); digitalWrite(STEP_IN4, LOW);
}

void moveStepperDir(int dir) {
  stepper.step(STEP_PER_WIN * dir);
  stepperPos += STEP_PER_WIN * dir;
  powerDownStepper();
}

void victorySpinStepper() {
  stepper.setSpeed(15);
  stepper.step(STEPS_PER_REV);
  stepper.setSpeed(STEPPER_RPM);
  if (stepperPos != 0) { stepper.step(-stepperPos); stepperPos = 0; }
  powerDownStepper();
}

void resetToIdle() {
  gameState = ST_IDLE;
  p1Wins = p2Wins = roundNum = 0;
  if (stepperPos != 0) { stepper.step(-stepperPos); stepperPos = 0; }
  powerDownStepper();
  servo.write(SERVO_IDLE);
  digitalWrite(BUZZER_PIN, LOW);
  buzzerOffAt = 0;
}

// ─────────────────────────────────────────────
//  AWARD + REPORT
// ─────────────────────────────────────────────
void awardAndReport(int winner, long s1, long s2, bool isFalse) {
  if (winner > 0) {
    if (winner == 1) p1Wins++; else p2Wins++;
    // Stepper tug-of-war moves every round — correct per task spec
    moveStepperDir(winner == 1 ? -1 : +1);
    // Servo only snaps to declare the FINAL game winner (3 wins)
    // Do NOT move servo here — handled below at game-over
  }

  String tag = (winner == 0) ? "NONE" : String(winner);
  String ft  = isFalse ? ",FALSE" : ",NORMAL";
  Serial.println("RESULT:" + tag + "," +
                 String(s1) + "," + String(s2) + "," +
                 String(p1Wins) + "," + String(p2Wins) + ft);

  if (winner > 0 && (p1Wins >= 3 || p2Wins >= 3)) {
    // Snap servo to winning player's side to declare champion
    servo.write(p1Wins >= 3 ? SERVO_P1 : SERVO_P2);
    delay(300);  // let servo reach position before victory spin blocks
    victorySpinStepper();
    String wName = (p1Wins >= 3) ? p1Name : p2Name;
    Serial.println("GAME_OVER:" + wName);
    // Victory beep — blocking here is fine, game is over
    digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW); delay(100);
    digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW); delay(100);
    digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW); delay(100);
    digitalWrite(BUZZER_PIN, HIGH); delay(600); digitalWrite(BUZZER_PIN, LOW);
    resetToIdle();
    return;
  }

  gameState   = ST_RESULT;
  resultUntil = millis() + 2000;
}

// ─────────────────────────────────────────────
//  BEGIN ROUND
// ─────────────────────────────────────────────
void beginRound() {
  cdRemain   = random(3, 21);
  cdNextBeep = millis() + 800;
  resetButtons();
  gameState  = ST_COUNTDOWN;
  Serial.println("ROUND_START");
  roundNum++;
}

// ─────────────────────────────────────────────
//  SETUP
// ─────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  pinMode(BTN1_PIN,   INPUT_PULLUP);
  pinMode(BTN2_PIN,   INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  servo.attach(SERVO_PIN);
  servo.write(SERVO_IDLE);
  stepper.setSpeed(STEPPER_RPM);
  randomSeed(analogRead(A0));
  Serial.println("READY");
}

// ─────────────────────────────────────────────
//  MAIN LOOP — fully non-blocking
//  No delay() calls anywhere except:
//  - victory beep (game already over)
//  - stepper.step() (unavoidable, motor physics)
// ─────────────────────────────────────────────
void loop() {

  // Always run buzzer scheduler first
  buzzerUpdate();

  // Always service serial
  if (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    if (msg.startsWith("START:")) {
      int comma = msg.indexOf(',', 6);
      if (comma > 6) {
        p1Name = msg.substring(6, comma);
        p2Name = msg.substring(comma + 1);
      }
      p1Wins = p2Wins = roundNum = stepperPos = 0;
      servo.write(SERVO_IDLE);
      beginRound();
    } else if (msg == "RESET") {
      resetToIdle();
    }
  }

  switch (gameState) {

    case ST_IDLE:
      break;

    // ── COUNTDOWN ──────────────────────────────
    // updateBtn() is non-blocking — no delay().
    // beepAsync() is non-blocking — no delay().
    // Loop runs at full speed (~16000x/sec).
    case ST_COUNTDOWN: {

      bool pressed1 = updateBtn(b1);
      bool pressed2 = updateBtn(b2);

      // False start detection
      if (pressed1 || pressed2) {
        int loser  = pressed1 ? 1 : 2;
        int winner = (loser == 1) ? 2 : 1;
        beepAsync(400);   // angry beep — non-blocking
        Serial.println("FALSE:" + String(loser));
        awardAndReport(winner, -1, -1, true);
        break;
      }

      // Countdown tick — fires once per second, no blocking
      if (millis() >= cdNextBeep) {
        cdRemain--;
        Serial.println("CD:" + String(cdRemain));
        cdNextBeep = millis() + 1000;

        if (cdRemain <= 0) {
          // BUZZ — snapshot button states then fire
          // Take snapshot before turning buzzer on
          // (buzzer power surge can glitch nearby pins)
          b1.wasHigh = (digitalRead(BTN1_PIN) == HIGH);
          b2.wasHigh = (digitalRead(BTN2_PIN) == HIGH);
          b1.fired = b2.fired = false;
          b1.pressing = b2.pressing = false;
          p1RT = p2RT = -1;
          p1Fired = p2Fired = false;

          // NOW fire buzzer — stays on until button pressed or timeout
          digitalWrite(BUZZER_PIN, HIGH);
          buzzerOffAt = 0;   // manual control during react phase
          buzzAt    = millis();
          gameState = ST_REACT;
          Serial.println("BUZZ");
        } else {
          beepAsync(50);   // short countdown tick — non-blocking
        }
      }
      break;
    }

    // ── REACT ──────────────────────────────────
    // Raw reads every loop — maximum responsiveness.
    // No debounce here — we want instant reaction capture.
    // A real human press lasts 50-200ms so no debounce needed.
    case ST_REACT: {
      bool r1 = (digitalRead(BTN1_PIN) == LOW);
      bool r2 = (digitalRead(BTN2_PIN) == LOW);

      // Update armed flags
      if (!r1) b1.wasHigh = true;
      if (!r2) b2.wasHigh = true;

      // Record reaction times — first press only, must be armed
      if (r1 && b1.wasHigh && !p1Fired) {
        p1RT    = (long)(millis() - buzzAt);
        p1Fired = true;
      }
      if (r2 && b2.wasHigh && !p2Fired) {
        p2RT    = (long)(millis() - buzzAt);
        p2Fired = true;
      }

      // End condition: both pressed or 10s timeout
      if ((p1Fired && p2Fired) || millis() - buzzAt > 10000UL) {
        digitalWrite(BUZZER_PIN, LOW);
        buzzerOffAt = 0;

        int  winner = 0;
        if      (p1RT >= 0 && p2RT >= 0) winner = (p1RT <= p2RT) ? 1 : 2;
        else if (p1RT >= 0)              winner = 1;
        else if (p2RT >= 0)              winner = 2;
        long s1 = (p1RT < 0) ? 0 : p1RT;
        long s2 = (p2RT < 0) ? 0 : p2RT;
        awardAndReport(winner, s1, s2, false);
      }
      break;
    }

    // ── RESULT PAUSE ───────────────────────────
    case ST_RESULT:
      if (millis() >= resultUntil) beginRound();
      break;
  }
}
