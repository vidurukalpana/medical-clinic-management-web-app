// Calm, joyful soundtrack for the demo, synthesised from scratch (no samples, copyright-free).
// Soft electric piano, marimba melody, music-box bells, gentle bass and light percussion in C major.
// Usage: node music.js <seconds> <out.wav>
const fs = require("fs");
const SR = 44100;
const DUR = parseFloat(process.argv[2] || "120");
const OUT = process.argv[3] || "music.wav";
const BPM = 96;
const BEAT = 60 / BPM, BAR = BEAT * 4;
const N = Math.ceil((DUR + 4) * SR);
const L = new Float32Array(N), R = new Float32Array(N);
const sendL = new Float32Array(N), sendR = new Float32Array(N);

const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
let seed = 7;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296) * 2 - 1;
const TAU = Math.PI * 2;

function put(i, l, r, send) {
  if (i < 0 || i >= N) return;
  L[i] += l; R[i] += r; sendL[i] += l * send; sendR[i] += r * send;
}

// I - V - vi - IV, voiced warmly with added ninths.
const CHORDS = [
  { root: 36, notes: [60, 64, 67, 74] }, // Cadd9
  { root: 43, notes: [59, 62, 67, 69] }, // G(add9)
  { root: 45, notes: [60, 64, 69, 71] }, // Am(add9)
  { root: 41, notes: [57, 60, 65, 67] }, // F(add9)
];

// Marimba melody: [beat, length in beats, midi]
const MELODY_A = [
  [[0, 1, 76], [1, 0.5, 79], [1.5, 0.5, 81], [2, 1, 79], [3, 1, 76]],
  [[0, 1.5, 74], [1.5, 0.5, 71], [2, 1, 74], [3, 1, 79]],
  [[0, 1, 72], [1, 1, 76], [2, 1.5, 81], [3.5, 0.5, 79]],
  [[0, 1, 77], [1, 0.5, 76], [1.5, 0.5, 74], [2, 2, 72]],
];
const MELODY_B = [
  [[0, 0.5, 79], [0.5, 0.5, 81], [1, 1, 84], [2, 1, 81], [3, 1, 79]],
  [[0, 1, 79], [1, 1, 74], [2, 1, 79], [3, 1, 83]],
  [[0, 1.5, 84], [1.5, 0.5, 83], [2, 1, 81], [3, 1, 76]],
  [[0, 1, 77], [1, 1, 81], [2, 1, 79], [3, 1, 76]],
];

function epiano(t0, m, dur, gain, pan = 0.5) {
  const f = mtof(m), s0 = Math.floor(t0 * SR), n = Math.floor((dur + 1.2) * SR);
  let pc = Math.random(), pm = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const rel = t > dur ? Math.exp(-(t - dur) * 6) : 1;
    const env = Math.min(1, t / 0.004) * Math.exp(-t * 1.6) * rel;
    const idx = 1.2 * Math.exp(-t * 7) + 0.25;
    pm += f / SR; pc += f / SR;
    const s = Math.sin(TAU * pc + idx * Math.sin(TAU * pm)) * env * gain * (1 + 0.06 * Math.sin(TAU * 4.5 * t));
    put(s0 + i, s * (1 - pan) * 1.4, s * pan * 1.4, 0.35);
  }
}

function marimba(t0, m, gain, pan = 0.5) {
  const f = mtof(m), s0 = Math.floor(t0 * SR), n = Math.floor(1.4 * SR);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const a = Math.min(1, t / 0.002);
    const s = a * (Math.sin(TAU * f * t) * Math.exp(-t * 3.2) + 0.35 * Math.sin(TAU * f * 4 * t) * Math.exp(-t * 18) +
      0.08 * Math.sin(TAU * f * 9.9 * t) * Math.exp(-t * 40)) * gain;
    put(s0 + i, s * (1 - pan) * 1.4, s * pan * 1.4, 0.45);
  }
}

function bell(t0, m, gain, pan) {
  const f = mtof(m), s0 = Math.floor(t0 * SR), n = Math.floor(2.2 * SR);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const s = Math.min(1, t / 0.002) * (Math.sin(TAU * f * t) * Math.exp(-t * 2.2) + 0.3 * Math.sin(TAU * f * 2.76 * t) * Math.exp(-t * 6)) * gain;
    put(s0 + i, s * (1 - pan) * 1.4, s * pan * 1.4, 0.7);
  }
}

function bass(t0, m, dur, gain) {
  const f = mtof(m), s0 = Math.floor(t0 * SR), n = Math.floor(dur * SR);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const env = Math.min(1, t / 0.01) * Math.min(1, (dur - t) / 0.05) * (0.75 + 0.25 * Math.exp(-t * 4));
    const s = (Math.sin(TAU * f * t) + 0.18 * Math.sin(TAU * 2 * f * t)) * env * gain;
    put(s0 + i, s, s, 0.05);
  }
}

function pad(t0, notes, dur, gain) {
  const s0 = Math.floor(t0 * SR), n = Math.floor(dur * SR);
  const v = notes.map((m) => ({ f: mtof(m), d: 1 + (Math.random() - 0.5) * 0.004 }));
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    const env = Math.min(1, t / 0.8) * Math.min(1, (dur - t) / 0.8);
    let l = 0, r = 0;
    for (const x of v) { l += Math.sin(TAU * x.f * t); r += Math.sin(TAU * x.f * x.d * t); }
    put(s0 + i, (l / v.length) * env * gain, (r / v.length) * env * gain, 0.6);
  }
}

function kick(t0, gain) {
  const s0 = Math.floor(t0 * SR), n = Math.floor(0.3 * SR); let ph = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR; ph += (50 + 60 * Math.exp(-t * 30)) / SR;
    const s = Math.sin(TAU * ph) * Math.exp(-t * 9) * gain;
    put(s0 + i, s, s, 0);
  }
}

function shaker(t0, gain, pan) {
  const s0 = Math.floor(t0 * SR), n = Math.floor(0.09 * SR); let prev = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR, w = rnd(), hp = w - prev; prev = w;
    const env = Math.min(1, t / 0.012) * Math.exp(-t * 45);
    put(s0 + i, hp * env * gain * (1 - pan), hp * env * gain * pan, 0.1);
  }
}

function snap(t0, gain) {
  const s0 = Math.floor(t0 * SR), n = Math.floor(0.12 * SR); let z1 = 0, z2 = 0;
  const f = 1800, q = 3, w0 = TAU * f / SR, alpha = Math.sin(w0) / (2 * q);
  const b0 = alpha, a1 = -2 * Math.cos(w0), a2 = 1 - alpha, a0 = 1 + alpha;
  let x1 = 0, x2 = 0;
  for (let i = 0; i < n; i++) {
    const t = i / SR, x = rnd() * Math.exp(-t * 38);
    const y = (b0 * x - b0 * x2 - a1 * z1 - a2 * z2) / a0;
    x2 = x1; x1 = x; z2 = z1; z1 = y;
    put(s0 + i, y * gain, y * gain, 0.5);
  }
}

const totalBars = Math.ceil(DUR / BAR);
for (let bar = 0; bar < totalBars; bar++) {
  const t = bar * BAR, ch = CHORDS[bar % 4], last = bar === totalBars - 1;
  const intro = bar < 4, outro = bar >= totalBars - 3;
  const rel = (bar - 4) % 24, brk = !intro && !outro && rel >= 20;
  const full = !intro && !outro && !brk && rel >= 8;

  // Electric piano comping: on 1, the "and" of 2, and 4.
  const hits = last ? [[0, 3.5]] : intro || brk ? [[0, 1.8], [2, 1.8]] : [[0, 1.3], [1.5, 0.9], [3, 0.9]];
  for (const [b, len] of hits) ch.notes.forEach((m, k) => epiano(t + b * BEAT + k * 0.012, m, len * BEAT, 0.085, 0.35 + k * 0.1));
  pad(t, ch.notes.map((m) => m - 12), BAR + 0.4, last ? 0.05 : 0.035);

  // Music-box sparkle in intro and breakdowns.
  if (intro || brk || outro) {
    const arp = [ch.notes[0] + 12, ch.notes[1] + 12, ch.notes[2] + 12, ch.notes[3] + 12];
    for (let s = 0; s < 4; s++) bell(t + (s * 2 + 1) * BEAT / 2, arp[s], 0.05, s % 2 ? 0.7 : 0.3);
  }

  if (!intro && !last) bass(t, ch.root, BEAT * 1.4, 0.32), bass(t + BEAT * 1.5, ch.root, BEAT * 0.4, 0.22), bass(t + BEAT * 2, ch.root + 7, BEAT * 1.8, 0.24);

  if (!intro && !brk && !outro) {
    const mel = (rel >= 8 && rel < 16 ? MELODY_B : MELODY_A)[bar % 4];
    for (const [b, , m] of mel) marimba(t + b * BEAT, m, 0.16, 0.55);
    for (let s = 0; s < 8; s++) shaker(t + s * BEAT / 2 + (s % 2 ? 0.02 : 0), s % 2 ? 0.03 : 0.018, s % 2 ? 0.65 : 0.4);
  }
  if (full) {
    for (let b = 0; b < 4; b++) kick(t + b * BEAT, b % 2 ? 0.35 : 0.5);
    snap(t + BEAT, 0.18); snap(t + BEAT * 3, 0.18);
  }
}

// Light stereo reverb on the send bus.
function reverb(x, off) {
  const out = new Float32Array(N);
  for (const d of [1557, 1617, 1491, 1422].map((d) => d + off)) {
    const buf = new Float32Array(d); let idx = 0, z = 0;
    for (let i = 0; i < N; i++) { const y = buf[idx]; z = y * 0.55 + z * 0.45; buf[idx] = x[i] + z * 0.8; idx = (idx + 1) % d; out[i] += y * 0.25; }
  }
  for (const d of [556 + off, 441 + off]) {
    const buf = new Float32Array(d); let idx = 0;
    for (let i = 0; i < N; i++) { const b = buf[idx]; const y = -out[i] + b; buf[idx] = out[i] + b * 0.5; idx = (idx + 1) % d; out[i] = y; }
  }
  return out;
}
const rvL = reverb(sendL, 0), rvR = reverb(sendR, 23);

const len = Math.floor(DUR * SR);
let peak = 0;
for (let i = 0; i < len; i++) {
  const t = i / SR, g = Math.min(1, t / 1.2) * Math.min(1, (DUR - t) / 3);
  L[i] = Math.tanh((L[i] + rvL[i] * 0.3) * 1.1) * g; R[i] = Math.tanh((R[i] + rvR[i] * 0.3) * 1.1) * g;
  peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
}
const norm = 0.85 / peak;
const buf = Buffer.alloc(44 + len * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + len * 4, 4); buf.write("WAVE", 8); buf.write("fmt ", 12);
buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22); buf.writeUInt32LE(SR, 24);
buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34); buf.write("data", 36); buf.writeUInt32LE(len * 4, 40);
for (let i = 0; i < len; i++) {
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * norm)) * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * norm)) * 32767), 46 + i * 4);
}
fs.writeFileSync(OUT, buf);
console.log(`wrote ${OUT} (${DUR}s, ${totalBars} bars)`);
