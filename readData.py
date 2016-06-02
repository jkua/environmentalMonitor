import serial
import json
import time
import datetime
import zmq

def printMessage(message, temperatureUnit='celsius'):
    dt = datetime.datetime.fromtimestamp(message['time'])
    
    timeString = dt.strftime('%Y-%m-%d %H:%M:%S')
    if temperatureUnit == 'celsius':
        temperatureString = 'Temperature: {:.2f} deg C'.format(message['temperature'])
    elif temperatureUnit == 'fahrenheit':
        temperatureString = 'Temperature: {:.2f} deg F'.format(message['temperature'] * 9./5. + 32)
    else:
        raise Exception('Unknown temperature unit! {}'.format(temperatureUnit))
    pressureString = 'Pressure: {:.2f} hPa'.format(message['pressure'])
    humidityString = 'Humidity: {:.2f}%'.format(message['humidity'])
    windString = 'Wind: {}'.format(message['wind'])
    print('[{}]: {}, {}, {}, {}'.format(timeString, temperatureString, pressureString, humidityString, windString))

class Publisher:
    def __init__(self, host='tcp://*:5559'):
        self.context = zmq.Context()

        # First, connect our subscriber socket
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(host)

      
    def send(self, message):
        self.publisher.send_pyobj(message)
    
if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('port')
    args = parser.parse_args()

    publisher = Publisher()

    ser = serial.Serial(args.port, 
                        baudrate=9600, 
                        bytesize=serial.EIGHTBITS, 
                        parity=serial.PARITY_NONE, 
                        stopbits=serial.STOPBITS_ONE, 
                        timeout=5)  # open serial port

    run = True
    while run:
        startTime = time.time()
        dt = datetime.datetime.fromtimestamp(startTime)
        outputFilename = 'data_{}.json'.format(dt.strftime('%Y%m%dT%H%M%S'))

        with open(outputFilename, 'w') as f:
            while 1:
                try:
                    messageJson = ser.readline()
                    message = json.loads(messageJson)
                    message['time'] = time.time()
                    f.write(json.dumps(message) + '\n')
                    printMessage(message, temperatureUnit='fahrenheit')
                    publisher.send(message)
                    # Start new file
                    if (datetime.datetime.now().hour == 0) and ((time.time()-startTime) > 4000):
                        break
                except ValueError:
                    print('Could not decode JSON! Got: {}'.format(messageJson))
                except KeyboardInterrupt:
                    run = False
                    break


