int led[] = {8 , 9 , 10 ,11 ,12}; //Asigna cada pin de la protoboard a un dedo 

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < 5; i++) {
    pinMode(led[i], OUTPUT);
  }
}

void loop() {
  if  (Serial.available() >= 5) {  //Hace que espere 5 bytes, 1 para cada dedo
      for (int i = 0; i < 5; i++) {
        int dedoEstado = Serial.read(); //Lee el estado del dedo, 0 o 1
        digitalWrite(led[i], dedoEstado == 1? HIGH : LOW); //apaga o prende la led
      }
    }
}