// --- Pines ---
const int GREEN_PINS[5] = {2, 3, 4, 5, 6};      // 5 azules
const int RED_PINS[5]  = {8, 9, 10, 11, 12};   // 5 rojos

void setup() {
  Serial.begin(9600);

  for (int i = 0; i < 5; i++) {
    pinMode(GREEN_PINS[i], OUTPUT);
    pinMode(RED_PINS[i], OUTPUT);
    digitalWrite(GREEN_PINS[i], LOW);
    digitalWrite(RED_PINS[i], LOW);
  }
}

void setAll(const int pins[5], int value) {
  for (int i = 0; i < 5; i++) digitalWrite(pins[i], value);
}

void setGreenFromFingers(byte dedos[5]) {
  for (int i = 0; i < 5; i++) digitalWrite(GREEN_PINS[i], dedos[i] ? HIGH : LOW);
}

bool readPacket(byte dedos[5], byte &status) {
  // Buscamos cabecera 'A'
  while (Serial.available() > 0) {
    int b = Serial.read();
    if (b == 'A') {
      // Esperamos 6 bytes más: 5 dedos + status
      unsigned long t0 = millis();
      while (Serial.available() < 6) {
        if (millis() - t0 > 200) return false; // timeout corto
      }
      for (int i = 0; i < 5; i++) dedos[i] = (byte)Serial.read();
      status = (byte)Serial.read();
      return true;
    }
  }
  return false;
}

void loop() {
  byte dedos[5] = {0,0,0,0,0};
  byte status = 0;

  if (!readPacket(dedos, status)) {
    return;
  }

  if (status == 1) {
    // Éxito: verdes ON, rojos OFF
    setAll(RED_PINS, LOW);
    setAll(GREEN_PINS, HIGH);
  } else if (status == 2) {
    // Fallo: rojos ON, verdes OFF
    setAll(GREEN_PINS, LOW);
    setAll(RED_PINS, HIGH);
  } else {
    // Lectura normal: verdes = dedos, rojos OFF
    setAll(RED_PINS, LOW);
    setBlueFromFingers(dedos);
  }
}
