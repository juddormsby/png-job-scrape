const COOKIE = '__Host-png_skills_session';
const SESSION_SECONDS = 8 * 60 * 60;
const encoder = new TextEncoder();

function privateHeaders(extra = {}) {
  return {
    'Cache-Control': 'private, no-store',
    'CDN-Cache-Control': 'no-store',
    'Netlify-CDN-Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'same-origin',
    ...extra,
  };
}

function encode(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
}

function decode(text) {
  if (!/^[A-Za-z0-9_-]{43}$/.test(text)) throw new Error('Invalid signature');
  return Uint8Array.from(atob(text.replaceAll('-','+').replaceAll('_','/')+'='),c=>c.charCodeAt(0));
}

async function keyFor(password, secret) {
  // Password rotation also invalidates existing sessions.
  return crypto.subtle.importKey('raw',encoder.encode(secret+'\0'+password),
    {name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
}

async function samePassword(provided, expected) {
  const [a,b] = await Promise.all([provided,expected].map(value=>crypto.subtle.digest('SHA-256',encoder.encode(value))));
  const x=new Uint8Array(a),y=new Uint8Array(b);
  let difference=0;
  for(let i=0;i<x.length;i++)difference|=x[i]^y[i];
  return difference===0;
}

function cookieValue(request) {
  return (request.headers.get('Cookie')||'').split(';').map(v=>v.trim()).find(v=>v.startsWith(COOKIE+'='))?.slice(COOKIE.length+1);
}

async function validSession(request, key) {
  const token=cookieValue(request);
  if(!token || token.length>200)return false;
  const parts=token.split('.');
  if(parts.length!==4)return false;
  const [version,expiry,nonce,signature]=parts;
  const seconds=Number(expiry),now=Math.floor(Date.now()/1000);
  if(version!=='v1'||!/^\d+$/.test(expiry)||!Number.isSafeInteger(seconds)||seconds<=now||seconds>now+SESSION_SECONDS||!/^[a-f0-9-]{36}$/.test(nonce))return false;
  try {
    return await crypto.subtle.verify('HMAC',key,decode(signature),encoder.encode(parts.slice(0,3).join('.')));
  } catch { return false; }
}

function safeNext(value, origin) {
  if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||/[\\\r\n]/.test(value))return '/';
  const destination=new URL(value,origin);
  if(destination.origin!==origin||destination.pathname.startsWith('/_access/'))return '/';
  return destination.pathname+destination.search+destination.hash;
}

function escape(value) {
  return value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function loginPage(next, wrong=false) {
  return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in | PNG skills</title><style>
  *{box-sizing:border-box}body{margin:0;background:#f3f6f6;color:#17344a;font:16px/1.5 Arial,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px;border-top:5px solid #00b6c9}main{width:100%;max-width:430px;background:white;padding:40px;border-top:5px solid #007db7;box-shadow:0 10px 50px #0025690c}.eyebrow{font-size:10px;font-weight:bold;letter-spacing:.15em;color:#007db7;margin:0 0 20px}h1{font-size:34px;line-height:1.12;letter-spacing:-.04em;color:#002569;margin:0 0 20px}p{font-size:14px;color:#5c6e7b}label{font-size:13px;font-weight:bold;display:block;margin:28px 0 8px}input{display:block;width:100%;padding:13px;border:1px solid #a9bfca;border-radius:3px;font:16px Arial;margin-bottom:18px}input:focus{outline:2px solid #007db7;outline-offset:2px}button{background:#002569;color:white;border:0;border-radius:3px;padding:13px 22px;width:100%;font:600 14px Arial;cursor:pointer}button:hover{background:#007db7}.error{color:#a63018;font-size:13px}.note{font-size:11px;margin-top:22px;margin-bottom:0}
  </style></head><body><main><p class="eyebrow">PNG LABOUR MARKET RESEARCH</p><h1>Skills in<br>PNG job adverts</h1><p>Enter the shared password to open the dashboard.</p><form action="/_access/login" method="post"><input type="hidden" name="next" value="${escape(next)}"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256" autofocus>${wrong?'<p class="error" role="alert">That password was not recognised. Please try again.</p>':''}<button type="submit">Open dashboard</button></form><p class="note">Your login lasts eight hours on this browser.</p></main></body></html>`,
    {status:401,headers:privateHeaders({'Content-Type':'text/html; charset=utf-8',
      'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})});
}

async function readForm(request) {
  const reader=request.body?.getReader();
  if(!reader)return null;
  const chunks=[];
  let size=0;
  for(;;){
    const {done,value}=await reader.read();
    if(done)break;
    size+=value.length;
    if(size>4096){await reader.cancel();return null;}
    chunks.push(value);
  }
  const bytes=new Uint8Array(size);
  let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  return new URLSearchParams(new TextDecoder().decode(bytes));
}

function redirect(location, cookie) {
  return new Response(null,{status:303,headers:privateHeaders({Location:location,...(cookie?{'Set-Cookie':cookie}:{})})});
}

export default async function passwordGate(request, context) {
  const password=Netlify.env.get('DASHBOARD_PASSWORD');
  const secret=Netlify.env.get('DASHBOARD_SESSION_SECRET');
  // A missing secret, unexpected runtime error or failed downstream request never bypasses authentication.
  if(!password||!secret||secret.length<32)return new Response('Access is temporarily unavailable.',{status:503,headers:privateHeaders()});
  const url=new URL(request.url),key=await keyFor(password,secret);
  if(url.pathname==='/_access/login'||url.pathname==='/_access/logout') {
    if(request.method!=='POST')return redirect('/');
    if(request.headers.get('Origin')!==url.origin)return new Response('Forbidden',{status:403,headers:privateHeaders()});
    if(url.pathname.endsWith('/logout'))return redirect('/',`${COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0`);
    if(!request.headers.get('Content-Type')?.startsWith('application/x-www-form-urlencoded'))return new Response('Invalid request',{status:400,headers:privateHeaders()});
    const form=await readForm(request);
    if(!form)return new Response('Invalid request',{status:400,headers:privateHeaders()});
    const next=safeNext(form.get('next'),url.origin);
    const provided=form.get('password')||'';
    if(provided.length>256||!await samePassword(provided,password))return loginPage(next,true);
    const payload=`v1.${Math.floor(Date.now()/1000)+SESSION_SECONDS}.${crypto.randomUUID()}`;
    const signature=encode(await crypto.subtle.sign('HMAC',key,encoder.encode(payload)));
    return redirect(next,`${COOKIE}=${payload}.${signature}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=${SESSION_SECONDS}`);
  }
  if(!await validSession(request,key)) {
    // Only browser page navigations get the form. Data and asset requests never receive their original contents.
    if(request.method==='GET'&&(request.headers.get('Accept')||'').includes('text/html'))return loginPage(safeNext(url.pathname+url.search,url.origin));
    return new Response('Password required.',{status:401,headers:privateHeaders({'Content-Type':'text/plain; charset=utf-8'})});
  }
  const response=await context.next();
  const headers=new Headers(response.headers);
  for(const [name,value] of Object.entries(privateHeaders()))headers.set(name,value);
  headers.set('Vary',[headers.get('Vary'),'Cookie'].filter(Boolean).join(', '));
  if(url.pathname.endsWith('.mjs'))headers.set('Content-Type','text/javascript; charset=utf-8');
  return new Response(response.body,{status:response.status,statusText:response.statusText,headers});
}

// No excluded paths, caching or fail-open fallback: pages, assets and JSON all require a session.
export const config = {path:'/*',onError:'fail'};
