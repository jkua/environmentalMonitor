import elitech
from elitech.msg import DataBodyRequest, DataBodyResponse
import math
import os
import json
import time
import datetime
from datetime import timedelta
import zmq

class ElitechDevice(elitech.Device):
    def __init__(self, serial_port):
        elitech.Device.__init__(self, serial_port)

    def getLatestPage(self, callback=None, page_size=None):
        """
        :type devinfo: DevInfoResponse
        :rtype:list[(int,datetime,float)]
        """
        devinfo = self.get_devinfo()
        header = self.get_data_header(devinfo.station_no)

        if page_size is None:
            if devinfo.model_no == 40: # RC-4
                page_size = 100
            elif devinfo.model_no == 50: #RC-5
                page_size = 500
            else:
                raise ValueError("Unknowm model_no (%d). can't decide page_size", devinfo.model_no)

        page = int(math.ceil(header.rec_count / float(page_size)))
        dt = timedelta(hours=devinfo.rec_interval.hour,
                      minutes=devinfo.rec_interval.minute,
                      seconds=devinfo.rec_interval.second)

        data_list = []
        base_time = devinfo.start_time + dt * (page-1) * page_size
        no = 1 + (page-1)
        try:
            self._ser.open()
            p = page-1
            
            req = DataBodyRequest(devinfo.station_no, p)
            count = page_size if (p+1) * page_size <= devinfo.rec_count else (devinfo.rec_count % page_size)
            res = DataBodyResponse(count)
            self._talk(req, res)

            for rec in res.records:
                data_list.append((no, base_time, rec/10.0))
                no += 1
                base_time += dt
            if callback is not None:
                callback(data_list)
                data_list = []
        finally:
            self._ser.close()
            time.sleep(self.wait_time)

        return data_list

class Elitech:
    def __init__(self, device):
        self.device = ElitechDevice(device)
        self.latest = 0

    def initialize(self, interval=(0,0,10)):
        success = False
        while not success:
            try:
                devinfo = self.device.get_devinfo()  # get current parameters.
                success = True
            except:
                print('Failed to get device info... retrying...')

        self.device.set_clock(devinfo.station_no, set_time=datetime.datetime.utcnow())
        self.setInterval(*interval)

    def setInterval(self, hours, minutes, seconds):
        devinfo = self.device.get_devinfo()  # get current parameters.

        param_put = devinfo.to_param_put()  #convart devinfo to parameter
        param_put.rec_interval = datetime.time(hours, minutes, seconds)    # update parameter

        param_put_res = self.device.update(param_put)    # update device

    def record(self, filename=None, path='.', host=None):
        if host is not None:
            publisher = Publisher(host=host)
        data = self.device.getLatestPage()
        if filename is None:
            filename = 'temp_{}.json'.format(data[0][1].strftime('%Y%m%dT%H%M%S'))
            os.path.join(path)
        with open(filename, 'w') as f:
            while True:
                try:
                    if data is None:
                        data = self.device.getLatestPage()
                    for record in data:
                        recordNumber, recordDatetime, temperature = record
                        if recordNumber <= self.latest:
                            continue
                        offset = recordDatetime - datetime.datetime(1970, 1, 1)
                        timestamp = offset.days*24*3600 + offset.seconds
                        recordDict = {'index': recordNumber,
                                      'time': timestamp,
                                      'temperature': temperature
                                     }
                        f.write(json.dumps(recordDict) + '\n')
                        print('{}:\t{}\t{:.1f}'.format(recordNumber, recordDatetime.strftime('%Y-%m-%d %H:%M:%S'), temperature))
                        if host is not None:
                            publisher.send(recordDict)

                        if (recordNumber - self.latest) > 1:
                            print('Missed record! Last: {}, Current: {}'.format(self.latest, record[0]))
                        self.latest = recordNumber
                    data = None
                except KeyboardInterrupt:
                    break
                except:
                    pass

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
    parser.add_argument('device', help='Specify device, e.g. /dev/tty.wchusbserial')
    args = parser.parse_args()

    print('Connecting to {}...'.format(args.device))
    reader = Elitech(args.device)

    print('Initializing...')
    reader.initialize()

    print('Start recorder by pressing and holding the play button for four seconds.')
    raw_input("Press Enter to continue...")

    reader.record(host='tcp://*:5558')
