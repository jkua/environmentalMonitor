# Environmental Monitor
Arduino code for monitoring environmental conditions. 

Based on an [Adafruit Feather M0 WiFi - ATSAMD21 + ATWINC1500](https://www.adafruit.com/product/3010) with a [Bosch BME280](https://www.adafruit.com/products/2652) temperature/humidity/pressure sensor and a [Modern Device Wind Sensor Rev. C](https://moderndevice.com/product/wind-sensor/). 

Simple data acquisition writes a JSON object over the USB serial port. Client software reads the JSON messages and writes them to disk as well as publishing them over ZeroMQ to a PyQt GUI.

Added reader for an Elitech RC-5 temperature logger based on the [elitech-datareader](https://github.com/civic/elitech-datareader).
