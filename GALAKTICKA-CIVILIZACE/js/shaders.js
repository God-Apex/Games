// GLSL shadery (WebGL2). Scéna se kreslí do HDR bufferu, pak bloom a tónování (ACES).
'use strict';

const GLSL_NOISE = `
float hash21(vec2 p){ p = fract(p*vec2(123.34, 456.21)); p += dot(p, p+45.32); return fract(p.x*p.y); }
float vnoise(vec2 p){ vec2 i=floor(p), f=fract(p); vec2 u=f*f*(3.-2.*f);
  float a=hash21(i), b=hash21(i+vec2(1,0)), c=hash21(i+vec2(0,1)), d=hash21(i+vec2(1,1));
  return mix(mix(a,b,u.x), mix(c,d,u.x), u.y); }
float fbm(vec2 p){ float s=0., a=.5; mat2 m=mat2(1.6,1.2,-1.2,1.6); for(int i=0;i<5;i++){ s+=a*vnoise(p); p=m*p; a*=.5; } return s; }
float fbm3(vec2 p){ float s=0., a=.5; mat2 m=mat2(1.6,1.2,-1.2,1.6); for(int i=0;i<3;i++){ s+=a*vnoise(p); p=m*p; a*=.5; } return s; }
`;

const SH = {};

SH.quadVS = `#version 300 es
layout(location=0) in vec2 aPos;
out vec2 vUv;
void main(){ vUv = aPos*.5+.5; gl_Position = vec4(aPos,0,1); }`;

SH.bgFS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform vec2 uRes, uOff; uniform float uTime, uNeb, uStars;
${GLSL_NOISE}
vec3 farStars(vec2 p, float cs, float thr, float b){
  vec2 c = floor(p/cs); vec2 f = p - c*cs;
  float h = hash21(c);
  if (h < thr) return vec3(0);
  vec2 sp = vec2(hash21(c+3.1), hash21(c+7.7))*cs;
  float d = length(f-sp);
  float tw = .75 + .25*sin(uTime*(1.+h*3.) + h*40.);
  vec3 col = mix(vec3(1.,.8,.6), vec3(.7,.8,1.), hash21(c+1.3));
  return col * b * tw * exp(-d*d*1.4) * (h-thr)/(1.-thr);
}
void main(){
  vec2 p = gl_FragCoord.xy + uOff;
  vec3 c = vec3(.0012,.0016,.0040);
  vec2 q = p / 900.;
  float n = fbm3(q*1.2 + vec2(uTime*.002, 0.)) + vnoise(q*9.6)*.06;
  float n2 = fbm3(q*2.7 + 11.3);
  float n3 = fbm3(q*.5 - 3.7);
  vec3 neb = mix(vec3(.10,.025,.16), vec3(.015,.07,.16), n2);
  neb = mix(neb, vec3(.12,.05,.03), smoothstep(.55,.8,n3)*.6);
  c += neb * pow(n, 3.5) * .35 * uNeb;
  c += farStars(p, 7., .985, .16) * uStars;
  c += farStars(p*.71+31., 13., .99, .35) * uStars;
  c += farStars(p*.53+77., 29., .995, .9) * uStars;
  o = vec4(c, 1.);
}`;

SH.spriteVS = `#version 300 es
layout(location=0) in vec2 aCorner;
layout(location=1) in vec4 iA;
layout(location=2) in vec4 iB;
layout(location=3) in vec4 iC;
layout(location=4) in float iD;
uniform vec2 uRes;
out vec2 vL; flat out vec4 vA; flat out vec4 vB; flat out vec4 vC; flat out float vD;
void main(){
  vec2 p = iA.xy + aCorner*iA.z;
  vL = aCorner*iA.z; vA=iA; vB=iB; vC=iC; vD=iD;
  gl_Position = vec4(p.x/uRes.x*2.-1., 1.-p.y/uRes.y*2., 0., 1.);
}`;

// iA: x, y, velikost čtverce (px), poloměr (px)
// iB: barva rgb, intenzita
// iC: druh, p1, p2, p3     iD: p4
SH.spriteFS = `#version 300 es
precision highp float;
in vec2 vL; flat in vec4 vA; flat in vec4 vB; flat in vec4 vC; flat in float vD;
uniform float uTime;
out vec4 o;
${GLSL_NOISE}
const float PI = 3.14159265;

vec4 star(vec2 l, float size, float r, vec3 col, float a, float glow, float spikes){
  float d = length(l);
  float fade = smoothstep(size, size*.55, d);
  float sig = max(glow, .55);
  float core = exp(-d*d/(2.*sig*sig));
  float halo = sig*sig/(d*d + sig*sig*1.5) * .12;
  vec3 c = col * a * (core*1.6 + halo) * fade;
  if (spikes > 0.) {
    float w = .7 + sig*.08;
    float sx = exp(-abs(l.y)/w) * exp(-abs(l.x)/(size*.3));
    float sy = exp(-abs(l.x)/w) * exp(-abs(l.y)/(size*.3));
    c += mix(col, vec3(1.), .4) * spikes * a * (sx + sy) * fade * .6;
  }
  float alpha = 0.;
  if (r > .5) {
    float e = d/r;
    if (e < 1.) {
      float mu = sqrt(1.-e*e);
      float limb = 1. - .6*(1.-mu) - .2*(1.-mu)*(1.-mu);
      vec2 q = l/r;
      float g = fbm(q*(r > 60. ? 4.5 : 7.) + vec2(uTime*.02, vD));
      float g2 = vnoise(q*35. + uTime*.15 + vD);
      vec3 surf = mix(col, vec3(1.), .08*mu) * limb * (.55 + .65*g + .12*g2);
      float edge = smoothstep(1., 1. - 1.6/r, e);
      c = mix(c, surf * (.6 + .05*a), edge);
      alpha = edge;
    } else {
      float x = d - r;
      float cor = exp(-x/(r*.03 + 1.)) * .55 + exp(-x/(r*.18 + 2.)) * .16 + exp(-x/(r*.8 + 4.)) * .04;
      float rays = .7 + .3*fbm(vec2(atan(l.y,l.x)*6., x/(r*.3+1.) - uTime*.05));
      c += col * cor * rays * fade;
    }
  }
  return vec4(c, alpha);
}

vec4 planet(vec2 l, float r, vec3 col, vec2 ld, float style, float atm, float seed){
  float d = length(l); float e = d/r;
  vec3 L = normalize(vec3(ld, .3));
  vec3 c = vec3(0.); float alpha = 0.;
  if (e < 1.) {
    vec2 q = l/r; float mu = sqrt(1.-e*e);
    vec3 n = vec3(q.x, -q.y, mu);
    float lam = max(dot(n, L), 0.);
    float term = smoothstep(-.05, .25, dot(n, L));
    vec3 base = col;
    if (style > 1.5 && style < 2.5) {            // Země: oceány, kontinenty, mraky
      float land = fbm(q*3. + seed);
      vec3 ground = mix(vec3(.18,.32,.12), vec3(.45,.38,.25), fbm(q*7.+seed));
      base = land > .53 ? ground : vec3(.04,.12,.32);
      base = mix(base, vec3(.95), smoothstep(.85, .95, e) * 0.);
      float cap = smoothstep(.22, .08, e);
      base = mix(base, vec3(.92,.95,1.), cap);   // pohled shora = pól
      float cl = fbm(q*4.5 + vec2(uTime*.01, seed*2.));
      base = mix(base, vec3(.95), smoothstep(.58, .8, cl)*.75);
    } else if (style > .5 && style < 1.5) {      // plynný obr při pohledu na pól: soustředné pásy a víry
      float ang = atan(q.y, q.x);
      float sw = fbm(vec2(ang*2., e*6.) + seed) * .25;
      float b = sin((e*e)*28. + sw*6. + seed);
      base = col * (.82 + .18*b);
      base = mix(base, col*vec3(1.1,.95,.85), smoothstep(.6,1.,fbm(q*9.+seed))*.3);
      float vort = smoothstep(.12, .0, length(q - vec2(.35*cos(seed), .35*sin(seed))));
      base = mix(base, vec3(.95,.6,.45), vort*.7);
    } else if (style > 2.5) {                    // ledové
      float f = fbm(q*5. + seed);
      base = mix(col*.85, vec3(.95,.97,1.), f);
    } else {                                     // kamenné: krátery a skvrny
      float f = fbm(q*4. + seed);
      float cr = smoothstep(.04,.0, abs(vnoise(q*12.+seed)-.5)-.01)*.06;
      base = col * (.7 + .5*f) - cr;
    }
    vec3 lit = base * (lam*.9 + .012);
    float rim = pow(1.-mu, 2.5) * atm;
    lit += vec3(.45,.65,1.)*mix(vec3(1.), col, .3) * rim * smoothstep(-.3, .4, dot(vec3(q.x,-q.y,0.), L)) * 1.2;
    c = lit;
    alpha = smoothstep(1., 1. - 1.5/r, e);
    c *= alpha;
  }
  if (atm > 0. && e >= .97 && e < 1.15) {
    vec2 q = l/d;
    float s = smoothstep(-.3, .5, dot(vec3(q.x,-q.y,0.), L));
    c += vec3(.4,.6,1.) * atm * exp(-(e-1.)*40.) * s * .7;
  }
  return vec4(c, alpha);
}

vec4 rings(vec2 l, float ri, float ro, vec2 ld, float pr, vec3 col){
  float d = length(l);
  if (d < ri || d > ro) return vec4(0.);
  float t = (d - ri)/(ro - ri);
  float b = .55 + .25*sin(t*90.) + .2*vnoise(vec2(t*160., 1.));
  b *= smoothstep(.0, .05, t) * smoothstep(1., .9, t);
  b *= 1. - .85*smoothstep(.015, .0, abs(t - .62));   // Cassiniho dělení
  vec2 dir = normalize(ld);
  float behind = dot(l, dir);
  float perp = abs(l.x*dir.y - l.y*dir.x);
  float sh = behind < 0. ? smoothstep(pr*.95, pr*1.05, perp) : 1.;
  float a = b*.75;
  return vec4(col * b * (.25 + .9*sh) * a, a);
}

vec4 blackhole(vec2 l, float rs, float disk, float size, float seed){
  float d = length(l);
  float rsh = 2.6*rs;
  vec3 back = vec3(0.), front = vec3(0.);
  back += vec3(1.,.86,.7) * exp(-pow((d-rsh)/(.05*rsh+.5), 2.)) * (.35 + disk*.9);
  back += vec3(.55,.65,1.) * .12 * exp(-abs(d - rsh*1.6)/(rsh*.6+1.));
  if (disk > 0.) {
    float inc = .2;
    vec2 q = vec2(l.x, l.y/inc);
    float dq = length(q);
    float rin = 3.*rs, rout = 22.*rs;
    float band = smoothstep(rin*.9, rin*1.25, dq) * smoothstep(rout, rin*3., dq);
    float ang = atan(q.y, q.x);
    float sw = fbm(vec2(ang*2.5 - uTime*.35 + log(dq/rs)*3., log(dq/rs)*5. + seed));
    float dop = clamp(1. + .75*(-q.x/(dq+1e-3)), .2, 2.);
    vec3 dc = mix(vec3(1.,.42,.12), vec3(1.,.93,.82), smoothstep(rout*.5, rin, dq));
    vec3 dl = dc * band * (.35 + 1.0*sw) * dop * disk * .85;
    if (l.y > 0.) front += dl; else back += dl;
    float arc = exp(-pow((d - rsh*1.18)/(rsh*.22), 2.)) * smoothstep(rsh*.2, -rsh*.9, l.y);
    back += dc * arc * disk * .9;
    float arc2 = exp(-pow((d - rsh*1.08)/(rsh*.12), 2.)) * smoothstep(-rsh*.1, rsh*.9, l.y);
    back += dc * arc2 * disk * .45;
  }
  float shadow = smoothstep(rsh*1.0, rsh*.9, d);
  vec3 c = back*(1. - shadow) + front;
  c *= smoothstep(size, size*.6, d);
  return vec4(c, shadow);
}

vec4 neutron(vec2 l, float r, vec3 col, float a, float ang, float size, float mag){
  float d = length(l);
  float rr = max(r, 1.);
  float core = exp(-d*d/(2.*rr*rr))*2.5 + 1.5/(d*d*.25 + 1.5)*.6;
  vec2 bd = vec2(cos(ang), sin(ang));
  float al = dot(l, bd); float pe = abs(l.x*bd.y - l.y*bd.x);
  float w = .5 + abs(al)*.07;
  float beam = exp(-pe*pe/(w*w)) * exp(-abs(al)/(size*.4));
  float cone = exp(-pe/(abs(al)*.35+1.)) * exp(-abs(al)/(size*.25)) * .25;
  vec3 c = col*core*a + vec3(.65,.78,1.)*(beam + cone)*a*1.4;
  if (mag > 0.) {
    float lines = abs(sin(atan(l.y,l.x)*2.)) * exp(-abs(d - size*.18*(.6+.4*sin(atan(l.y,l.x)*2.)))/(3.));
    c += vec3(.75,.35,1.) * lines * .5 * a;
  }
  return vec4(c * smoothstep(size, size*.6, d), 0.);
}

// galaxie: typ 0 spirála, 1 eliptická, 2 nepravidelná, 3 Mléčná dráha (model z galaxy.js)
uniform vec4 uMW;   // ARM_PHI0, PITCH, ARM_R0, BAR_ANGLE
vec4 galaxy(vec2 l, float r, vec3 col, float a, float type, float rot, float cosi, float seed){
  vec2 u = l / r;
  float cr = cos(rot), sr = sin(rot);
  u = vec2(u.x*cr - u.y*sr, u.x*sr + u.y*cr);
  u.y /= max(cosi, .12);
  float R = length(u);
  if (R > 1.25) return vec4(0.);
  vec3 c = vec3(0.);
  if (type > 2.5) {
    vec2 k = vec2(l.x, -l.y) / r * 16.;      // kpc, střed v Sgr A*
    float Rk = length(k) + 1e-4;
    float phi = atan(k.y, k.x);
    float disc = exp(-Rk/3.2) * smoothstep(17., 11., Rk);
    float psi = phi - log(Rk/uMW.z)/uMW.y - uMW.x;
    float wob = (fbm(k*.35 + 3.) - .5)*2.2 + (fbm(k*1.3 + 8.) - .5)*.8;
    float main = pow(.5 + .5*cos(2.*psi + wob), 4.);
    float minor = pow(.5 + .5*cos(4.*psi + wob*1.4 + .4), 10.) * .3;
    float arms = mix(.5, .12 + 1.7*(main + minor), smoothstep(uMW.z*.45, uMW.z*1.05, Rk));
    vec2 ub = vec2(-cos(uMW.w), sin(uMW.w));
    float al = dot(k, ub), ac = -k.x*ub.y + k.y*ub.x;
    float bar = 2.2*exp(-al*al/(2.*2.4*2.4) - ac*ac/(2.*.65*.65));
    float bulge = 3.*exp(-Rk*Rk/(2.*.75*.75));
    float dust = pow(.5 + .5*cos(2.*psi + wob - .45), 14.) * smoothstep(2.5, 5., Rk);
    float grain = fbm(k*5. + seed);
    float clumps = smoothstep(.45, .85, fbm(k*1.7 + 2.));
    vec3 armC = mix(vec3(.38,.55,1.), vec3(.85,.9,1.), grain*.7);
    c += armC * disc * arms * (.45 + .9*grain*clumps + .3*grain) * (1. - dust*.85);
    float hii = smoothstep(.7, .88, fbm(k*2.6 + 9.)) * main * disc;
    c += vec3(1., .3, .5) * hii * 2.2;
    c += vec3(1., .78, .5) * (bar + bulge) * (.75 + .35*grain);
    c += vec3(1.,.85,.65) * disc * .12;
    c *= .32;
  } else if (type > 1.5) {
    float n = fbm(u*3. + seed);
    float m = exp(-R*R*3.) * smoothstep(.35, .7, n);
    c = mix(vec3(.6,.7,1.), vec3(1.,.5,.7), smoothstep(.75,.9,fbm(u*6.+seed)) ) * m * 1.5;
  } else if (type > .5) {
    c = vec3(1., .85, .65) * exp(-pow(R*7., .55)*2.2) * 4.;
  } else {
    float th = atan(u.y, u.x);
    float psi = th - log(R*8. + .2)/.25 + seed;
    float arms = pow(.5 + .5*cos(2.*psi + fbm(u*3.+seed)*1.5), 4.);
    float disc = exp(-R*4.5);
    float bulge = exp(-R*R*90.)*3.;
    c = (mix(vec3(.6,.72,1.), vec3(1.,.95,.9), .4) * disc * (.25 + 1.4*arms) + vec3(1.,.85,.6)*bulge) * (.6 + .4*fbm(u*12.+seed));
    c += vec3(1.,.35,.5) * smoothstep(.75,.92, fbm(u*7.+seed)) * arms * disc * 2.;
  }
  return vec4(c * a * col * smoothstep(1.25, .9, R), 0.);
}

vec4 shell(vec2 l, float r, float cov, vec3 col){
  float e = length(l)/r;
  if (e > 1.04) return vec4(0.);
  float mu = sqrt(max(1. - e*e, 0.));
  vec2 q = l/r / (.35 + .65*mu) * 9.;
  vec2 s = vec2(1., 1.7320508), h = s*.5;
  vec2 ga = mod(q, s) - h, gb = mod(q - h, s) - h;
  vec2 gv = dot(ga,ga) < dot(gb,gb) ? ga : gb;
  vec2 id = q - gv;
  float hd = max(dot(abs(gv), normalize(s)), abs(gv.x));
  float edge = .5 - hd;
  float filled = step(hash21(id*.37 + 1.3), cov);
  vec3 c = vec3(0.);
  float frame = smoothstep(.07, .0, edge) * min(1., cov*6. + .25);
  c += vec3(1., .78, .4) * frame * .55;
  c += filled * (vec3(.9, .32, .12)*.22 + vec3(1.,.85,.6) * pow(hash21(id + floor(uTime*.5)), 30.) * .8);
  c += vec3(1., .6, .3) * pow(1. - mu, 5.) * .5 * min(1., cov*3. + .2);
  return vec4(c * smoothstep(1.04, .99, e), 0.);
}

vec4 nebula(vec2 l, float r, vec3 col, float a, float seed){
  float e = length(l)/r;
  if (e > 1.3) return vec4(0.);
  vec2 q = l/r;
  float f = fbm(q*3. + seed);
  float rid = 1. - abs(fbm(q*7. + seed*2.)*2. - 1.);
  float sh = smoothstep(1.3, .8, e) * (.25 + .75*smoothstep(.1, .9, e));
  vec3 c = col * sh * (f*.35 + pow(rid, 7.)*1.4) + vec3(.6,.75,1.)*exp(-e*e*30.)*.5;
  return vec4(c * a, 0.);
}

void main(){
  int k = int(vC.x + .5);
  vec4 c;
  if (k == 0) c = star(vL, vA.z, vA.w, vB.rgb, vB.a, vC.y, vC.z);
  else if (k == 1) c = planet(vL, vA.w, vB.rgb, vC.yz, vC.w, vD, vB.a);
  else if (k == 2) c = neutron(vL, vA.w, vB.rgb, vB.a, vC.y, vA.z, vC.z);
  else if (k == 3) c = blackhole(vL, vA.w, vC.y, vA.z, vC.z);
  else if (k == 4) c = galaxy(vL, vA.w, vB.rgb, vB.a, vC.y, vC.z, vC.w, vD);
  else if (k == 5) c = shell(vL, vA.w, vB.a, vB.rgb);
  else if (k == 6) c = rings(vL, vA.w, vC.y, vC.zw, vD, vB.rgb);
  else if (k == 9) c = nebula(vL, vA.w, vB.rgb, vB.a, vC.y);
  else {  // 7: měkká tečka
    float d = length(vL); float s = max(vA.w, .6);
    c = vec4(vB.rgb * vB.a * exp(-d*d/(2.*s*s)), 0.);
  }
  o = c;
}`;

// předpočítaná textura (Mléčná dráha) kreslená jako obdélník na obrazovce
SH.texVS = `#version 300 es
layout(location=0) in vec2 aPos;
uniform vec2 uRes, uCenter, uHalf;
out vec2 vUv;
void main(){ vUv = aPos*.5+.5; vec2 p = uCenter + aPos*uHalf; gl_Position = vec4(p.x/uRes.x*2.-1., 1.-p.y/uRes.y*2., 0., 1.); }`;
SH.texFS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uTex; uniform float uA;
void main(){ o = vec4(texture(uTex, vec2(vUv.x, 1.-vUv.y)).rgb * uA, 0.); }`;

SH.downFS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uTex; uniform vec2 uTexel;
void main(){
  vec2 t = uTexel;
  vec3 c = texture(uTex, vUv).rgb*4.;
  c += texture(uTex, vUv + vec2(-t.x,-t.y)).rgb + texture(uTex, vUv + vec2(t.x,-t.y)).rgb;
  c += texture(uTex, vUv + vec2(-t.x,t.y)).rgb + texture(uTex, vUv + vec2(t.x,t.y)).rgb;
  o = vec4(c/8., 1.);
}`;

SH.upFS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uTex; uniform vec2 uTexel;
void main(){
  vec2 t = uTexel;
  vec3 c = texture(uTex, vUv + vec2(-t.x*2., 0.)).rgb + texture(uTex, vUv + vec2(t.x*2., 0.)).rgb
         + texture(uTex, vUv + vec2(0., -t.y*2.)).rgb + texture(uTex, vUv + vec2(0., t.y*2.)).rgb;
  c += (texture(uTex, vUv + vec2(-t.x, t.y)).rgb + texture(uTex, vUv + vec2(t.x, t.y)).rgb
      + texture(uTex, vUv + vec2(-t.x, -t.y)).rgb + texture(uTex, vUv + vec2(t.x, -t.y)).rgb) * 2.;
  o = vec4(c/12., 1.);
}`;

SH.compFS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uScene, uBloom; uniform float uExposure, uBloomK, uTime;
vec3 aces(vec3 x){ return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14), 0., 1.); }
void main(){
  vec3 c = texture(uScene, vUv).rgb + texture(uBloom, vUv).rgb * uBloomK;
  c = aces(c * uExposure);
  float lu = dot(c, vec3(.2126, .7152, .0722));
  c = clamp(mix(vec3(lu), c, 1.35), 0., 1.);
  vec2 v = vUv - .5;
  c *= 1. - dot(v, v)*.55;
  c = pow(c, vec3(1./2.2));
  float n = fract(sin(dot(gl_FragCoord.xy + uTime, vec2(12.9898, 78.233)))*43758.5453);
  c += (n - .5)/255.;
  o = vec4(c, 1.);
}`;
