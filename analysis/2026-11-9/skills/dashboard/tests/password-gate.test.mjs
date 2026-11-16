import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../netlify/edge-functions/password-gate.js',import.meta.url),'utf8');
const {default:gate,config}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const origin='https://dashboard.example';
const password='local-test-password';
const secret='independent-signing-secret-for-automated-tests';
let environment={DASHBOARD_PASSWORD:password,DASHBOARD_SESSION_SECRET:secret};
globalThis.Netlify={env:{get:key=>environment[key]}};
let calls=0;
const context={next:async()=>{calls++;return new Response('protected-content',{headers:{'Cache-Control':'public, max-age=3600'}});}};
const login=(value=password,next='/')=>new Request(origin+'/_access/login',{method:'POST',
  headers:{Origin:origin,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password:value,next})});
async function session(){const r=await gate(login(),context);return r.headers.get('Set-Cookie').split(';')[0];}

test('every path is protected and runtime errors fail closed',()=>{
  assert.deepEqual(config,{path:'/*',onError:'fail'});
});

test('unauthenticated pages get only the password form',async()=>{
  calls=0;
  const r=await gate(new Request(origin+'/?filter=x',{headers:{Accept:'text/html'}}),context);
  assert.equal(r.status,401);assert.equal(calls,0);
  const html=await r.text();assert.ok(html.includes('type="password"'));assert.ok(!html.includes('protected-content'));
  assert.ok(!html.includes(password));assert.ok(!html.includes(secret));
  assert.equal(r.headers.get('Cache-Control'),'private, no-store');
});

test('direct JSON, code, encoded paths, HEAD and query strings cannot bypass login',async()=>{
  calls=0;
  for(const path of ['/data/dashboard.json','/data/details/0.json','/index.html','/app.mjs','/data%2Fdashboard.json','/?download=1']){
    for(const method of ['GET','HEAD']){
      const r=await gate(new Request(origin+path,{method}),context);
      assert.equal(r.status,401);assert.equal(await r.text(),'Password required.');
    }
  }
  assert.equal(calls,0);
});

test('wrong passwords never create a session',async()=>{
  const r=await gate(login('incorrect'),context);
  assert.equal(r.status,401);assert.equal(r.headers.get('Set-Cookie'),null);
  assert.ok((await r.text()).includes('not recognised'));
});

test('correct password creates a secure signed cookie and redirects locally',async()=>{
  const r=await gate(login(password,'/?selection=foo#adverts'),context);
  assert.equal(r.status,303);assert.equal(r.headers.get('Location'),'/?selection=foo#adverts');
  const cookie=r.headers.get('Set-Cookie');
  for(const flag of ['__Host-','Secure','HttpOnly','SameSite=Strict','Path=/','Max-Age=28800'])assert.ok(cookie.includes(flag));
  assert.ok(!cookie.includes(password));assert.ok(!cookie.includes(secret));
});

test('signed session permits assets and data but disables browser and CDN caching',async()=>{
  const cookie=await session();calls=0;
  for(const path of ['/','/data/details/0.json','/app.mjs']){
    const r=await gate(new Request(origin+path,{headers:{Cookie:cookie}}),context);
    assert.equal(r.status,200);assert.equal(await r.text(),'protected-content');
    assert.equal(r.headers.get('Cache-Control'),'private, no-store');
    assert.equal(r.headers.get('Netlify-CDN-Cache-Control'),'no-store');
    assert.ok(r.headers.get('Vary').includes('Cookie'));
  }
  assert.equal(calls,3);
});

test('tampered, fabricated and expired cookies do not grant access',async()=>{
  const cookie=await session();
  const [,token]=cookie.split('=');
  const expiredPayload=`v1.${Math.floor(Date.now()/1000)-1}.${crypto.randomUUID()}`;
  const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(secret+'\0'+password),{name:'HMAC',hash:'SHA-256'},false,['sign']);
  const sig=Buffer.from(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(expiredPayload))).toString('base64url');
  calls=0;
  for(const value of ['bad',token.replace('v1.','v2.'),token.slice(0,-5)+'AAAAA',`${expiredPayload}.${sig}`]){
    const r=await gate(new Request(origin+'/data/dashboard.json',{headers:{Cookie:`__Host-png_skills_session=${value}`}}),context);
    assert.equal(r.status,401);
  }
  assert.equal(calls,0);
});

test('password rotation invalidates existing sessions; missing configuration blocks access',async()=>{
  const cookie=await session();
  environment={DASHBOARD_PASSWORD:'rotated',DASHBOARD_SESSION_SECRET:secret};
  assert.equal((await gate(new Request(origin+'/',{headers:{Cookie:cookie}}),context)).status,401);
  environment={};
  assert.equal((await gate(new Request(origin+'/'),context)).status,503);
  environment={DASHBOARD_PASSWORD:password,DASHBOARD_SESSION_SECRET:secret};
});

test('cross-site posts and unsafe redirect targets are rejected',async()=>{
  const cross=new Request(origin+'/_access/login',{method:'POST',headers:{Origin:'https://other.example','Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password})});
  assert.equal((await gate(cross,context)).status,403);
  for(const target of ['https://other.example','//other.example','/\\other.example','/_access/logout','/\r\nLocation: x']){
    const r=await gate(login(password,target),context);assert.equal(r.headers.get('Location'),'/');
  }
});

test('logout clears the cookie and oversized login requests are rejected',async()=>{
  const logout=await gate(new Request(origin+'/_access/logout',{method:'POST',headers:{Origin:origin}}),context);
  assert.equal(logout.status,303);assert.ok(logout.headers.get('Set-Cookie').includes('Max-Age=0'));
  assert.equal((await gate(login('x'.repeat(5000)),context)).status,400);
});
