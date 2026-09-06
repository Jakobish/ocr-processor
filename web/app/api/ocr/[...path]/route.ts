import {NextRequest} from 'next/server';
import {identity} from '../../../../lib/identity';
import {isSameOrigin,validBackendPath} from '../../../../lib/security';
export const dynamic='force-dynamic';
async function proxy(req:NextRequest,context:{params:Promise<{path:string[]}>}){
 const {path}=await context.params;
 if(!validBackendPath(path))return new Response(null,{status:400});
 if(!['GET','HEAD'].includes(req.method)&&!isSameOrigin(req.headers.get('origin'),process.env.OCR_PUBLIC_ORIGIN))return new Response(null,{status:403});
 try{
  const {token,profile}=await identity();
  const headers=new Headers({Authorization:`Bearer ${token}`,'X-OCR-Team':profile.tenant_id});
  for(const key of ['content-type','idempotency-key','range']){const value=req.headers.get(key);if(value)headers.set(key,value);}
  const base=process.env.OCR_API_URL;if(!base)return Response.json({detail:'API unavailable'},{status:503});
  const init:RequestInit&{duplex?:string}={method:req.method,headers,cache:'no-store',redirect:'manual',signal:req.signal};
  if(!['GET','HEAD'].includes(req.method)){init.body=req.body;init.duplex='half';}
  const upstream=await fetch(`${base.replace(/\/$/,'')}/api/v1/${path.join('/')}${req.nextUrl.search}`,init);
  const outgoing=new Headers({'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'});
  for(const key of ['content-type','content-disposition','content-length','content-range','accept-ranges']){const value=upstream.headers.get(key);if(value)outgoing.set(key,value);}
  if(path.includes('artifacts'))outgoing.set('Content-Security-Policy',"sandbox; default-src 'none'");
  return new Response(upstream.body,{status:upstream.status,headers:outgoing});
 }catch(e){return Response.json({detail:e instanceof Error&&e.message==='unauthenticated'?'Authentication required':'Service unavailable'},{status:e instanceof Error&&e.message==='unauthenticated'?401:503});}
}
export {proxy as GET,proxy as POST,proxy as PATCH,proxy as DELETE};
