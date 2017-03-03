import json
import os.path
import datetime

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    f = open(args.filename, 'r')
    records = []
    for line in f:
        record = json.loads(line.strip())
        if len(record.keys()) > 0:
            records.append(record)

    print('Read {} records'.format(len(records)))

    basename, ext = os.path.splitext(args.filename)
    outputFilename = basename + '.csv'

    print('Writing to {}'.format(outputFilename))
    with open(outputFilename, 'w') as f:
        header = ['index', 'time', 'datetime_utc', 'temperature']
        f.write(','.join(header) + '\n')

        for record in records:
            output = []
            for field in header:
                if field in record:
                    output.append(str(record[field]))
                else:
                    if field == 'datetime_utc':
                        timestamp = float(record['time'])
                        dt = datetime.datetime.utcfromtimestamp(timestamp)
                        dtString = dt.strftime('%Y-%m-%d %H:%M:%S')
                        output.append(dtString)
                    else:
                        raise ValueError('{} is not a supported header field!'.format(field))

            f.write(','.join(output) + '\n')

 