"""Only root-invoked immutable-source byte transfer; no ML or case imports."""
import hashlib,os,time,urllib.request,urllib.error,urllib.parse
ALLOWED={'huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.hf.co','cas-bridge.xethub.hf.co','us.aws.cdn.hf.co'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def stream(url,dest,declaration,events,deadline):
 """No retries; redirects are new recorded GETs, no signedquery is published."""
 opener=urllib.request.build_opener(NoRedirect());source=url
 for hop in range(4):
  if time.monotonic()>=deadline:raise TimeoutError('ACQUISITION_NETWORK_DEADLINE')
  parsed=urllib.parse.urlparse(source)
  if parsed.scheme!='https'or parsed.hostname not in ALLOWED or parsed.username or parsed.password:raise ValueError('UNREVIEWED_DOWNLOAD_ROUTE')
  if len(events)>=24:raise ValueError('GET_CAP24_EXHAUSTED')
  event={'at_monotonic':time.monotonic(),'host':parsed.hostname,'route_sha256':hashlib.sha256(source.encode()).hexdigest(),'hop':hop,'credentials_supplied':False,'status':None,'body_bytes':0};events.append(event)
  request=urllib.request.Request(source,headers={'User-Agent':'RuVector-free-source-acquisition/40','Accept':'application/octet-stream'})
  try:response=opener.open(request,timeout=max(.001,min(20,deadline-time.monotonic())))
  except urllib.error.HTTPError as error:response=error
  with response:
   event['status']=response.status
   if response.status in (301,302,303,307,308):
    target=response.headers.get('Location');response.read(0)
    if not target or hop==3:raise ValueError('REDIRECT_BOUND_OR_LOCATION_MISSING')
    source=urllib.parse.urljoin(source,target);continue
   if response.status!=200:raise ValueError('PUBLIC_SOURCE_HTTP_STATUS_'+str(response.status))
   count=0
   with dest.open('xb')as out:
    while True:
     if time.monotonic()>=deadline:raise TimeoutError('ACQUISITION_NETWORK_DEADLINE')
     block=response.read(1048576)
     if not block:break
     count+=len(block);event['body_bytes']=count
     if count>declaration['bytes']:raise ValueError('PUBLISHER_PAYLOAD_SIZE_EXCEEDED')
     out.write(block)
    out.flush();os.fsync(out.fileno())
   if count!=declaration['bytes']:raise ValueError('PUBLISHER_PAYLOAD_SIZE_INCOMPLETE')
   return
 raise ValueError('REDIRECT_BOUND_EXHAUSTED')
