import pyqtgraph as pg
from PyQt4 import QtGui, QtCore
import pytz
import time
import datetime
from pysigma.data.tools.time import Time
import json
import numpy as np
import zmq

pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOptions(antialias=True)

class Subscriber:
    def __init__(self, host='tcp://localhost:5559'):
        self.context = zmq.Context()

        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(host)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b'')

        self.poller = zmq.Poller()
        self.poller.register(self.subscriber, zmq.POLLIN)

    def receive(self):
        socks = dict(self.poller.poll(0))
        if self.subscriber in socks and socks[self.subscriber] == zmq.POLLIN:
            message = self.subscriber.recv_pyobj()
            return message
        else:
            return None

class TimeAxisItem(pg.AxisItem):
    def __init__(self, tzString=None, *args, **kwargs):
        pg.AxisItem.__init__(self, *args, **kwargs)

        if tzString is not None:
            self.tz = pytz.timezone(tzString)
        else:
            self.tz = None

    def tickSpacing(self, minVal, maxVal, size):
        # print('Size: {}'.format(size))
        valRange = maxVal - minVal
        numTicks = size/200
        majorTickSpacing = max(np.round(valRange/numTicks), 1)
        #                                             1m  2m   5m   10m  15m  20m   30m   1h,   2h,   6h,    12h,   24h
        spacings = np.array([1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600, 900, 1200, 1800, 3600, 7200, 21600, 43200, 86400])
        idx = spacings <= majorTickSpacing
        majorTickSpacing = spacings[idx][-1]
        #                         1,  2,  5, 10, 15, 20, 30, 1m, 2m, 5m, 10m, 15m, 20m, 30m, 1h,  2h,   6h,   12h,   24h
        minorSpacings = np.array([.2, .5, 1, 2,  5,  5,  5,  15, 30, 60, 120, 300, 300, 600, 900, 1800, 3600, 21600, 21600])
        minorTickSpacing = minorSpacings[idx][-1]        
        #                            1,   2,  5,  10,15,20,30,1m,2m, 5m, 10m, 15m, 20m, 30m, 1h,  2h,   6h,   12h,   24h
        subMinorSpacings = np.array([.1, .25, .2, 1, 1, 1, 1, 5,  5, 15, 30,  60,  60,  120, 300, 300,  900,  3600,  3600])
        subMinorTickSpacing = subMinorSpacings[idx][-1]

        return [(majorTickSpacing,0), (minorTickSpacing,0), (subMinorTickSpacing,0)]
 
    def tickStrings(self, values, scale, spacing):
        dt = Time.convertTimestampToDatetime(values, tz=self.tz)
        
        #return ['{}{:06.3f}'.format(t.strftime('%d %b %H:%M:'), t.second+t.microsecond/1e6) for t in dt]
        if spacing == 0.25:
            return ['{}{:05.2f}'.format(t.strftime('%H:%M:'), t.second+t.microsecond/1e6) for t in dt]
        elif spacing < 1:
            return ['{}{:04.1f}'.format(t.strftime('%H:%M:'), t.second+t.microsecond/1e6) for t in dt]
        elif spacing < 3600*6:
            return [t.strftime('%H:%M:%S') for t in dt]
        else:
            return [t.strftime('%d %b %H:%M') for t in dt]

class TimeSeriesPlot(pg.PlotWidget):
    def __init__(self, parent=None, tzString=None, ylabel=None):
        axis = TimeAxisItem(tzString=tzString, orientation='bottom')
        axis.enableAutoSIPrefix(False)
        pg.PlotWidget.__init__(self, parent=parent, axisItems={'bottom': axis})

        self.tzString = tzString

        self.setTimezoneLabel()

        self.viewBox = self.plotItem.vb

        self.plotHandleDict = {}

        self.showGrid(x=True, y=True)

    def setYLabel(self, label):
        axis = self.getAxis('left')
        axis.setLabel(label)

    def setTimezoneLabel(self, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
                
        if self.tzString:
            self.tz = pytz.timezone(self.tzString)
            localizedDt = Time.convertTimestampToDatetime(timestamp, tz=self.tzString)
            tzName = localizedDt.strftime('%Z')
            tzOffset = localizedDt.strftime('%z')
            tzOffset = '{}:{}'.format(tzOffset[:3], tzOffset[3:])
        else:
            self.tz = None
            tzName = 'Local'
            tzOffset = '+?'       
        
        axis = self.getAxis('bottom')
        axis.setLabel('Time {} (UTC{})'.format(tzName, tzOffset))
        axis.enableAutoSIPrefix(False)

    def update(self, timestamps, data, plotName='main', plotOptions={}):
        if plotName not in self.plotHandleDict:
            self.plotHandleDict[plotName] = self.plot(timestamps, data, **plotOptions)
        else:
            self.plotHandleDict[plotName].setData(x=timestamps, y=data)


class MainWindow(QtGui.QMainWindow):
    def __init__(self, tzString, tempUnit='celsius', tempOffset=0.):
        super(MainWindow, self).__init__()

        self.tzString = tzString
        self.tempUnit = tempUnit
        self.tempOffset = tempOffset

        self.temperaturePlot = TimeSeriesPlot(tzString=self.tzString)
        self.humidityPlot = TimeSeriesPlot(tzString=self.tzString)
        self.pressurePlot = TimeSeriesPlot(tzString=self.tzString)
        self.windPlot = TimeSeriesPlot(tzString=self.tzString)
        self.setupPlots()

        self.timeSeriesSplitter = QtGui.QSplitter(QtCore.Qt.Vertical)
        self.timeSeriesSplitter.addWidget(self.temperaturePlot)
        self.timeSeriesSplitter.addWidget(self.pressurePlot)
        self.timeSeriesSplitter.addWidget(self.windPlot)
        self.timeSeriesSplitter.addWidget(self.humidityPlot)

        self.setCentralWidget(self.timeSeriesSplitter)

        self.data = {}
        self.tempData = {}

        self.subscriber = Subscriber()
        self.tempSubscriber = Subscriber(host='tcp://localhost:5558')

        # Timer for checking the queue
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000) # milliseconds

    def setupPlots(self):
        self.temperaturePlot.setTitle('Temperature')
        self.temperaturePlot.setYLabel('Degrees {}'.format(self.tempUnit[0].upper()))
        self.humidityPlot.setTitle('Humidity')
        self.humidityPlot.setYLabel('% RH')
        self.pressurePlot.setTitle('Pressure')
        self.pressurePlot.setYLabel('hPa')
        self.windPlot.setTitle('Wind Speed')
        self.windPlot.setYLabel('Raw ADC')

        # Connect time axes
        temperaturePlotViewBox = self.temperaturePlot.viewBox
        self.humidityPlot.viewBox.setXLink(temperaturePlotViewBox)
        self.pressurePlot.viewBox.setXLink(temperaturePlotViewBox)
        self.windPlot.viewBox.setXLink(temperaturePlotViewBox)

    def plotData(self, data):
        self.data = data
        tempData = data['temperature']
        if self.tempUnit == 'fahrenheit':
            tempData = np.array(tempData) * 9./5. + 32 + self.tempOffset
        self.temperaturePlot.update(data['time'], tempData, plotOptions={'pen': (255, 0, 0)})
        self.humidityPlot.update(data['time'], data['humidity'], plotOptions={'pen': (0, 255, 0)})
        self.pressurePlot.update(data['time'], data['pressure'], plotOptions={'pen': (255, 127, 0)})
        self.windPlot.update(data['time'], data['wind'], plotOptions={'pen': (0, 0, 255)})

    def plotTempData(self, data):
        self.tempData = data
        tempData = data['temperature']
        if self.tempUnit == 'fahrenheit':
            tempData = np.array(tempData) * 9./5. + 32
        self.temperaturePlot.update(data['time'], tempData, plotName='External', plotOptions={'pen': (0, 0, 255)})
        
    def update(self):
        message = self.subscriber.receive()
        if message is not None:
            self.appendMessage(message, self.data)
            self.plotData(self.data)
        tempMessage = self.tempSubscriber.receive()
        if tempMessage is not None:
            print tempMessage
            self.appendMessage(tempMessage, self.tempData)
            self.plotTempData(self.tempData)

    def appendMessage(self, message, dataDict):
        for key, value in message.iteritems():
            if key not in dataDict:
                dataDict[key] = []
            dataDict[key].append(value)

        
if __name__=='__main__':
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--filenames', '-f', nargs='+', default=[], help='Data filenames')
    parser.add_argument('--timezone', '-z', default='US/Eastern')
    parser.add_argument('--tempOffset', type=float, default=-5.0)
    args = parser.parse_args()

    data = {}
    args.filenames = sorted(args.filenames)
    for filename in args.filenames:    
        print('Loading data from {}...'.format(filename))
        f = open(filename, 'r')
        for line in f:
            try:
                dataDict = json.loads(line.strip())
                for key, value in dataDict.iteritems():
                    if key not in data:
                        data[key] = []
                    data[key].append(value)
            except:
                pass

    print('Done - pushing to display...')

    app = QtGui.QApplication(sys.argv)
    mainWindow = MainWindow(args.timezone, tempUnit='fahrenheit', tempOffset=args.tempOffset)
    if data != {}:
        mainWindow.plotData(data)
    mainWindow.show()
    sys.exit(app.exec_())