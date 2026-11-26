"""Public read-only API gateway. Stateless Vercel Function. No private credentials."""
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from time import time
import re, json, logging

SOURCES={
 'extended':'https://api.starknet.extended.exchange/api/v1/info/markets',
 'variational':'https://omni-client-api.prod.ap-northeast-1.variational.io/metadata/v2/stats',
 'arcus':'https://api.arcus.xyz/v1/markets',
 'info':'https://api.hyperliquid.xyz/info',
}
TTL={'extended':90,'variational':300,'arcus':90,'info':0}
ALLOWED_HL={'perpDexs','metaAndAssetCtxs','l2Book','fundingHistory'}
MAX_BYTES=12_000_000

def valid_hl(body):
 if not isinstance(body,dict) or body.get('type') not in ALLOWED_HL:return False
 if body['type']=='metaAndAssetCtxs':return not body.get('dex') or (isinstance(body['dex'],str) and bool(re.fullmatch(r'[a-zA-Z0-9_-]{1,50}',body['dex'])))
 if body['type'] in ('fundingHistory','l2Book'):
  if not isinstance(body.get('coin'),str) or not re.fullmatch(r'[A-Za-z0-9_:\-.]{1,90}',body['coin']):return False
  if body['type']=='fundingHistory':return all(isinstance(body.get(k),int) and 0<body[k]<4_200_000_000_000 for k in ('startTime','endTime'))
 return True

class APIError(Exception):
 def __init__(self,status,message,retry=0):self.status=status;self.message=message;self.retry=retry

def fetch_provider(source,payload=None):
 data=json.dumps(payload).encode('utf-8') if payload is not None else None
 req=Request(SOURCES[source],data=data,method='POST' if data is not None else 'GET',headers={
  'User-Agent':'DN-Radar/1.0' if source=='variational' else 'EntropyIntelligence/5.2 independent research',
  'Accept':'application/json','Content-Type':'application/json'})
 try:
  with urlopen(req,timeout=14) as resp:
   raw=resp.read(MAX_BYTES+1)
  if len(raw)>MAX_BYTES:raise APIError(502,'Provider response too large')
  json.loads(raw)
  return raw
 except HTTPError as e:
  retry=0
  if e.code==429:
   try:retry=int(float(e.headers.get('Retry-After','0')))
   except (TypeError,ValueError):pass
   retry=max(60,min(1800,retry or 180))
  raise APIError(e.code,'Provider HTTP '+str(e.code),retry)
 except (URLError,TimeoutError,ValueError,OSError):
  raise APIError(502,'Provider unavailable / invalid response')

class BaseAPIHandler(BaseHTTPRequestHandler):
 source=None
 def send(self,status,data,headers=None):
  if isinstance(data,str):data=data.encode('utf-8')
  self.send_response(status)
  self.send_header('Content-Type','application/json; charset=utf-8')
  self.send_header('Content-Length',str(len(data)))
  self.send_header('Cache-Control','no-store')
  self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Referrer-Policy','no-referrer')
  for k,v in (headers or {}).items():self.send_header(k,str(v))
  self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.source=='info':return self.send(405,'{"error":"POST required"}')
  try:
   raw=fetch_provider(self.source)
   # Vercel CDN caching only on validated provider success. This is not durable history.
   self.send(200,raw,{'CDN-Cache-Control':f'max-age={TTL[self.source]}',
                      'X-Data-Stale':'false','X-Data-Updated':int(time()),
                      'X-Data-Note':'CDN cached response; timestamp of origin fetch'})
  except APIError as e:
   h={'Retry-After':e.retry} if e.retry else None
   self.send(e.status,json.dumps({'error':e.message,'retry_after_seconds':e.retry}),h)
 def do_POST(self):
  if self.source!='info':return self.send(405,'{"error":"GET required"}')
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length<2 or length>2048:raise ValueError()
   payload=json.loads(self.rfile.read(length))
   if not valid_hl(payload):raise ValueError()
  except (ValueError,TypeError,UnicodeDecodeError):return self.send(400,'{"error":"invalid request"}')
  try:self.send(200,fetch_provider('info',payload),{'X-Data-Updated':int(time()),'X-Data-Note':'Time of successful collection, not funding settlement'})
  except APIError as e:self.send(e.status,json.dumps({'error':e.message,'retry_after_seconds':e.retry}),{'Retry-After':e.retry} if e.retry else None)
 def log_message(self,*a):pass
