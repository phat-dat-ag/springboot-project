"""Protocol fixture only, not a real Loki/OpenSearch backend. No host port."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import gzip
import json
import signal
import sys
from pathlib import Path

EVENTS=Path('/lab/sink-events.jsonl')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def do_GET(self):
        data=EVENTS.read_text() if EVENTS.exists() else ''
        raw=json.dumps([json.loads(line) for line in data.splitlines()]).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        raw=self.rfile.read(int(self.headers['Content-Length']))
        if self.headers.get('Content-Encoding')=='gzip':
            raw=gzip.decompress(raw)
        rows=[]
        if 'push' in self.path:
            for stream in json.loads(raw)['streams']:
                rows += [json.loads(line) for _,line in stream['values']]
            backend='loki'
        else:
            lines=raw.decode().splitlines()
            operations=[next(iter(json.loads(lines[i]))) for i in range(0,len(lines),2)]
            rows=[json.loads(lines[i]) for i in range(1,len(lines),2)]
            backend='opensearch'
        with EVENTS.open('a') as output:
            for row in rows:
                output.write(json.dumps({'backend':backend,'record':row})+'\n')
        response=b'' if backend=='loki' else json.dumps({'took':1,'errors':False,'items':[
            {op:{'_index':'fixture','_id':row['correlationId'],'status':201,'result':'created'}}
            for op,row in zip(operations,rows)]}).encode()
        self.send_response(204 if backend=='loki' else 200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(response)))
        self.end_headers()
        self.wfile.write(response)

signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
HTTPServer(('0.0.0.0',9020),Handler).serve_forever()
