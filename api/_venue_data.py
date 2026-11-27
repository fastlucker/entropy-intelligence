"""Read-only per-venue public depth and funding history proxy. Fixed upstream hosts."""
from http.server import BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, parse_qs, quote, urlencode
import json, re, time

MAX_BYTES = 2_500_000
MARKET_RE = re.compile(r'^[A-Za-z0-9._:-]{1,85}$')
HOSTS = {'Arcus':'https://api.arcus.xyz', 'Extended':'https://api.starknet.extended.exchange'}

class Handler(BaseHTTPRequestHandler):
    mode = None
    def reply(self,code,body):
        data=json.dumps(body, separators=(',',':'),allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','public, s-maxage=15, stale-while-revalidate=10' if code==200 and self.mode=='book' else ('public, s-maxage=120' if code==200 else 'no-store'))
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        q=parse_qs(urlparse(self.path).query)
        venue=q.get('venue',[''])[0]
        market=q.get('market',[''])[0]
        if venue not in HOSTS or not MARKET_RE.fullmatch(market):
            return self.reply(400,{'error':'Invalid venue or market'})
        try:
            if venue=='Arcus':
                url=HOSTS[venue]+('/v1/l2OrderBook/'+quote(market,safe='') if self.mode=='book' else '/v1/fundingRates?'+urlencode({'market':market,'limit':'100'}))
            else:
                url=HOSTS[venue]+('/api/v1/info/markets/'+quote(market,safe='')+'/orderbook' if self.mode=='book' else '/api/v1/info/'+quote(market,safe='')+'/funding?'+urlencode({'startTime':int(time.time()*1000)-74*3600000,'endTime':int(time.time()*1000),'limit':150}))
            req=Request(url,headers={'Accept':'application/json','User-Agent':'EntropyIntelligence/5.7 research'})
            with urlopen(req, timeout=12) as res:
                raw=res.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: return self.reply(502,{'error':'Upstream payload too large'})
            data=json.loads(raw)
            if self.mode=='history':
                rows=data.get('fundingRates',[]) if venue=='Arcus' else data.get('data',[])
                if not isinstance(rows,list):raise ValueError('Missing funding records')
                out=[]
                for r in rows:
                    if not isinstance(r,dict):continue
                    t=r.get('time') if venue=='Arcus' else r.get('T')
                    rate=r.get('fundingRate') if venue=='Arcus' else r.get('f')
                    try:
                        t=float(t);rate=float(rate)
                        # Arcus microseconds; Extended docs sample uses Unix seconds, some versions milliseconds.
                        if t>1e14:t/=1000
                        elif t<1e11:t*=1000
                        if t>0 and abs(rate)<2:out.append({'time':round(t),'fundingRate':rate})
                    except (TypeError,ValueError,OverflowError):continue
                return self.reply(200,{'venue':venue,'market':market,'rows':out,'source':'public settled funding history','collectedAt':round(time.time()*1000)})
            rawbook=data.get('data',{}) if venue=='Extended' else data
            if not isinstance(rawbook,dict):raise ValueError('Unexpected orderbook shape')
            bids=rawbook.get('bids',rawbook.get('bid',[]));asks=rawbook.get('asks',rawbook.get('ask',[]))
            def levels(items,reverse):
                out=[]
                for r in items if isinstance(items,list) else []:
                    try:
                        if isinstance(r,list):px,sz=float(r[0]),float(r[1])
                        else:px,sz=float(r.get('price',r.get('px'))),float(r.get('qty',r.get('size',r.get('sz'))))
                        if px>0 and sz>0:out.append({'px':px,'sz':sz})
                    except (TypeError,ValueError,IndexError,AttributeError):continue
                out.sort(key=lambda x:x['px'],reverse=reverse)
                return out[:250]
            return self.reply(200,{'venue':venue,'market':market,'levels':[levels(bids,True),levels(asks,False)],'source':'public orderbook snapshot','collectedAt':round(time.time()*1000)})
        except HTTPError as e:self.reply(502,{'error':'Upstream HTTP '+str(e.code),'venue':venue})
        except (URLError,TimeoutError,OSError,ValueError,KeyError,json.JSONDecodeError) as e:self.reply(502,{'error':'Public market data unavailable: '+str(e)[:160],'venue':venue})
    def log_message(self,*a):pass
