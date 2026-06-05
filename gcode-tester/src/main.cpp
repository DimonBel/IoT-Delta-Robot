#include <Arduino.h>

namespace {
const unsigned long RESPONSE_DELAY_MS = 250;
const char *POSITION_RESPONSE = "-4.67,-5.81,-738.29,45.00,45.00,45.00";
String buffer;

void sendResponse(const String &response, const String &echo) {
  delay(RESPONSE_DELAY_MS);
  Serial.println(response);
  Serial.println(echo);
}

void handleCommand(const String &command) {
  if (command.length() == 0) {
    return;
  }

  if (command.startsWith("Position")) {
    sendResponse(POSITION_RESPONSE, command);
    return;
  }

  if (command.startsWith("IsDelta")) {
    sendResponse("YesDelta", command);
    return;
  }

  if (command.startsWith("G01") || command.startsWith("G28")) {
    sendResponse("Ok", command);
    return;
  }

  sendResponse("Ok", command);
}
} // namespace

void setup() {
  Serial.begin(115200);
}

void loop() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r' || c == '\n') {
      String command = buffer;
      buffer = "";
      handleCommand(command);
    } else {
      buffer += c;
    }
  }
}