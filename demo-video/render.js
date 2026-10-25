// Turns a recorded take into an MP4: real frame timing, sped-up waits and music.
// Usage: node render.js <take dir> <out.mp4> [global speed] [music file]
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const ffmpeg = require("ffmpeg-static");

// An optional music file is repeated with crossfades to the video's length; without one, music.js composes a track.
const [take, out, globalSpeedArg, musicFile] = process.argv.slice(2);
const GLOBAL = parseFloat(globalSpeedArg || "1");
const { frames, marks } = JSON.parse(fs.readFileSync(path.join(take, "timeline.json"), "utf8"));
const end = marks.find((m) => m.kind === "end").ts + 0.3;

// Speed changes, from "fast" marks (value = speed factor from that moment on).
const speedMarks = marks.filter((m) => m.kind === "fast").map((m) => ({ ts: m.ts, v: m.value }));
const speedAt = (ts) => {
  let v = 1;
  for (const m of speedMarks) if (m.ts <= ts) v = m.v;
  return v * GLOBAL;
};

const list = [];
let total = 0;
const usable = frames.filter((f) => f.ts <= end);
for (let i = 0; i < usable.length; i++) {
  const next = i + 1 < usable.length ? usable[i + 1].ts : end;
  const d = (next - usable[i].ts) / speedAt(usable[i].ts);
  if (d <= 0) continue;
  list.push(`file '${path.resolve(take, "frames", usable[i].file)}'\nduration ${d.toFixed(5)}`);
  total += d;
}
list.push(`file '${path.resolve(take, "frames", usable.at(-1).file)}'`);
fs.writeFileSync(path.join(take, "concat.txt"), list.join("\n"));
console.log(`video length ${total.toFixed(1)}s`);

let musicInputs, audioFilter;
if (musicFile) {
  const probe = require("child_process").spawnSync(ffmpeg, ["-hide_banner", "-i", musicFile], { encoding: "utf8" }).stderr;
  const [h, m, sec] = probe.match(/Duration: (\d+):(\d+):([\d.]+)/).slice(1).map(Number);
  const trackLength = h * 3600 + m * 60 + sec, cross = 4;
  const copies = Math.max(1, Math.ceil((total - cross) / (trackLength - cross)));
  musicInputs = Array.from({ length: copies }, () => ["-i", musicFile]).flat();
  let chain = "", last = "[1:a]";
  for (let k = 2; k <= copies; k++) { chain += `${last}[${k}:a]acrossfade=d=${cross}:c1=tri:c2=tri[x${k}];`; last = `[x${k}]`; }
  audioFilter = `${chain}${last}atrim=0:${total.toFixed(2)},asetpts=N/SR/TB,loudnorm=I=-16:TP=-1.5:LRA=11,aformat=sample_rates=48000:channel_layouts=stereo,` +
    `afade=t=in:st=0:d=0.8,afade=t=out:st=${(total - 4).toFixed(2)}:d=4[a]`;
} else {
  const music = path.join(take, "music.wav");
  execFileSync("node", [path.join(__dirname, "music.js"), String(Math.ceil(total) + 1), music], { stdio: "inherit" });
  musicInputs = ["-i", music];
  audioFilter = `[1:a]afade=t=out:st=${(total - 3).toFixed(2)}:d=3[a]`;
}

execFileSync(ffmpeg, [
  "-y", "-hide_banner", "-loglevel", "error",
  "-f", "concat", "-safe", "0", "-i", path.join(take, "concat.txt"),
  ...musicInputs,
  "-filter_complex", `[0:v]fps=30,scale=1920:1080:flags=lanczos,format=yuv420p,fade=t=in:st=0:d=0.6[v];${audioFilter}`,
  "-map", "[v]", "-map", "[a]",
  "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-movflags", "+faststart",
  "-c:a", "aac", "-b:a", "256k",
  "-t", total.toFixed(2),
  out,
], { stdio: "inherit" });
console.log(`wrote ${out}`);
