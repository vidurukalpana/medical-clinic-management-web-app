# Demo video

Records a music-only walkthrough of CareFlow (patient site, booking, live queue, chat assistant, staff portal and doctor portal) as a 1080p MP4.

```bash
cd demo-video
npm install
./make-video.sh                 # saves ~/Desktop/CareFlow-demo.mp4
```

Run it with `docker compose up` running, the demo data loaded, Ollama serving `llama3.2:1b` and Google Chrome installed.

- The clinic only consults on weekdays, so a temporary API container runs with its clock moved to Monday 26 Oct 2026, 08:15 (`DEMO_NOW` in `make-video.sh`). The real stack is left alone. If that Monday has passed, choose another weekday and update `DEMO_START` in `common.js` to match.
- The database is backed up before recording and restored afterwards. That copy of the API also has rate limiting turned off, so the chat conversation can't be cut short.
- The chat assistant runs on a small local model that sometimes gets a detail wrong. `record.js` checks each answer and records again if one is off.
- The soundtrack is downloaded on first run: "Inspiring Advertising - Upbeat Summer Corporate" by Rafael Krux, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit it wherever the video is posted:
  > Music: "Inspiring Advertising – Upbeat Summer Corporate" by Rafael Krux (filmmusic.io), CC BY 4.0
- To try another track on the last take, run `node render.js take out.mp4 1.1 <music file>`. Leave out the music file to use the track `music.js` composes.
- `record.js` holds the script of scenes and captions.
