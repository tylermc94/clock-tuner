# 🕰️ Clock Tuner

A microphone-based rate analyzer for mechanical clocks — like the *ClockMaster*
iPhone app, but a free single web page you host yourself. Hold a phone (or
laptop) near a ticking clock and it tells you:

- **Rate** — how many **seconds per day** the clock runs **fast or slow**
- **Beat rate (BPH)** — the measured beats-per-hour
- **Beat error** — how uneven the *tick* and *tock* are (in milliseconds)
- **Plain-language guidance** — which way to move the pendulum, and (if you enter
  the pendulum length) roughly **how many millimetres** to adjust

It runs entirely in the browser — no app store, no account, no data leaves the
device. It works great on an **iPhone in Safari**, and also on any laptop browser.

---

## The fastest way to use it on an iPhone

The browser will only give a web page microphone access over a **secure (https)
connection** (or on `localhost`). So the one requirement is serving `index.html`
over https. Pick whichever of these fits:

### Option A — deploy on Portainer (recommended for you, Tyler)

This repo ships a `docker-compose.yml` that serves the app with nginx.

1. In **Portainer → Stacks → Add stack**, choose **Repository**.
2. **Repository URL:** `https://github.com/<owner>/clock-tuner`
   **Compose path:** `docker-compose.yml`
3. **Deploy the stack.** Portainer clones the repo onto the Docker host and
   starts the container. The app is now on `http://<docker-host>:8099`.
   *(To pick up future updates, use the stack's **Pull and redeploy** / enable
   auto-update / GitOps polling.)*
4. **Add HTTPS** — the microphone will not work over plain http. Point your
   existing reverse proxy at the container:
   - **Nginx Proxy Manager:** New Proxy Host → domain `clock.yourdomain`,
     forward to `<docker-host>` port `8099`, request a Let's Encrypt cert,
     enable "Force SSL".
   - **Traefik:** uncomment the Traefik labels in `docker-compose.yml`, set your
     domain, and remove the `ports:` block (Traefik reaches it on the internal
     network).
5. Open `https://clock.yourdomain` on the iPhone in Safari → **Share → Add to
   Home Screen**. It launches full-screen like a real app, and mic access works.

> No reverse proxy yet? The quickest all-in-one is **Caddy**, which fetches a
> cert automatically — point a `clock.yourdomain` A record at your host and give
> Caddy a one-line `reverse_proxy <docker-host>:8099`.

There's also a `Dockerfile` if you'd rather build a portable image than mount a
file (`docker build -t clock-tuner . && docker run -d -p 8099:80 clock-tuner`).

### Option B — GitHub Pages (zero-effort, but public)
GitHub Pages gives free https. **Note:** it would publish whatever folder you
point it at, so only do this from a *public* repo or a dedicated repo that only
contains this app — don't enable Pages on your private vault repo. Then browse to
`https://<user>.github.io/<repo>/clock-tuner/`.

### Option C — quick local test on a laptop
`localhost` counts as secure, so on the same machine:
```bash
cd clock-tuner
python3 -m http.server 8099
# open http://localhost:8099  (mic works because it's localhost)
```
This is only for the laptop itself; phones on the LAN still need https (Option A/B).

---

## How to get a good reading

1. Enter the clock's **target beat rate (BPH)** — see below.
2. Put the phone's mic **close to the movement** (6–12 in / 15–30 cm), in a quiet
   room. Turn on **Do Not Disturb**.
3. Tap **Start listening** and allow the microphone.
4. Watch the **beat flash** and the level meter to confirm it's hearing ticks. If
   it isn't catching every tick, nudge the **Sensitivity** slider down; if it
   fires on noise, nudge it up.
5. Give it **20–30 beats** to stabilize. The reading settles as more beats come in.

### What "beat rate (BPH)" do I enter?
BPH (beats per hour) is a **property of the movement** — what it's *designed* to
run at — not something you choose. Common reference: a **1-second "seconds
pendulum" is 3600 BPH** (one tick every second). Check the movement's paperwork or
any stamp on it.

**Getting this right matters.** The mic measures the beat *interval* very
precisely, but "fast/slow" is only ever *relative to the target BPH you enter*. If
the target is wrong for your movement, the "seconds per day" figure will be wildly
off (e.g. a 6600-BPH clock read against the 3600 default shows tens of thousands
of s/day — that's the mismatch, not the clock). The app now warns you when the
measured rate is far from your target.

Don't know the BPH? Open **"What beat rate should I use?"** — there are two tools:

- **Use the measured tick rate** — reads how fast the clock is beating right now
  and sets that as the target (once the reading has settled, so it doesn't
  jitter). This is only correct **if the clock is currently keeping good time** —
  the tick can't distinguish the designed rate from a regulation error, and a
  movement's design BPH is set by its gear train, so it isn't necessarily a round
  number. Use it only as a rough starting point.
- **Calibrate from observed drift** *(most accurate)* — the mic alone can't know
  the intended rate, so anchor it to reality: tell it how far the clock has
  drifted against a reference (e.g. *gained 10 min over 1.5 days*) and it computes
  the **exact** target BPH. After that the reading matches your real-world
  observation and the pendulum advice is correct. (For a clock running fast, the
  true rate is slightly *below* the rate you measure at the tick.)

---

## Reading the beat trace

The scrolling graph plots each beat's timing **deviation from the target rate**:

- **Slope** of the dots = the rate error. Sloping up = running fast, down = slow,
  flat = on rate.
- **Tick** (gold) and **tock** (blue) form two lines. The **vertical gap** between
  them is the **beat error** — you want them nearly on top of each other.

This is the same picture professional timing machines (Tickoprint, Microset) draw.

---

## Calibrating from the reading

- **Running fast** → *lengthen* the pendulum: turn the rating nut under the bob so
  the bob moves **down**. (A longer pendulum swings slower.)
- **Running slow** → *shorten* the pendulum: turn the nut so the bob moves **up**.
- **Out of beat** (beat error more than a few ms) → the *tick* and *tock* are
  unevenly spaced. Make sure the clock is **level**, then adjust the **crutch /
  beat-setting lever** until the beat error drops under ~5 ms. A clock badly out of
  beat can stop.

If you enter the **pendulum length**, the app also estimates the length change in
millimetres. The physics: a pendulum's period `T ∝ √L`, so to change the rate by a
fraction `f`, change the length by `2·f`. To cancel a fast error of `S` seconds per
day: `ΔL = 2 · (S / 86400) · L` (lengthen if fast, shorten if slow).

> Adjust in **small steps** and let the clock run for **several hours to a day**
> between adjustments, then re-measure. The mic reading is precise *right now*, but
> real timekeeping is best confirmed over a long run against a reference clock.

---

## How it works (for the curious)

1. **Capture** — the Web Audio API reads raw mic samples. Echo cancellation, noise
   suppression, and auto-gain are all switched **off** so they don't smear the
   sharp tick transient.
2. **Detect** — a per-sample streaming detector computes a fast envelope (the
   click) over a slow envelope (the room noise). Because it triggers on the
   **ratio** of the two, the same settings work whether the recording is loud or
   faint. Each tick's time is taken at the envelope peak, sample-accurate.
3. **Analyze** — inter-tick intervals are outlier-filtered (dropping missed/double
   beats), then **averaged** to get the beat period → BPH and the rate vs. your
   target. Odd/even intervals are compared to get beat error.

### Trust / testing
The detection and rate math is unit-tested. `tools/validate_dsp.py` is a Python
port of the exact algorithm; it generates synthetic clock audio with a **known**
rate and beat error (plus noise and timing jitter) and asserts the analyzer
recovers them. The browser JavaScript was checked against the same synthetic audio
and produces matching numbers (BPH within ~0.05, rate within a few s/day, beat
error within ~0.3 ms).

```bash
pip install numpy
python3 tools/validate_dsp.py
```

---

## Limitations

- Needs a reasonably **quiet room** — ticking clocks, chimes, and chatter confuse
  the detector.
- The **rate** number is only as right as the **target BPH** you give it; the mic
  measures the beat interval precisely, but "fast/slow" is always relative to the
  intended rate.
- Best for **pendulum and balance clocks** with a clear tick. Very soft or muffled
  movements may need the phone closer and the sensitivity lowered.
