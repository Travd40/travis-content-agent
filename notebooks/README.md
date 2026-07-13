# Notebooks

## LivePortrait_Batch.ipynb — character performance transfer (free, Colab T4)

Open-source equivalent of Runway Act-Two for dialogue shots: a character still +
a video of you performing the line → the character performs your movements and
expressions. Best for close-ups and medium talking shots; the body stays mostly
still, so use Flow/Runway generation for shots that need real body movement.

**Use it:** [colab.research.google.com](https://colab.research.google.com) →
File → Upload notebook → pick `LivePortrait_Batch.ipynb` → Runtime → Change
runtime type → **T4 GPU** → run cells 1–4 top to bottom.

**Job folder format** (one image + one video per folder, any file names):

```
jobs/
  01_terrence_heaven/
      terrence.png        ← character still
      me_performing.mp4   ← your driving video
  02_marcus_reply/
      ...
```

Zip the `jobs` folder and upload it in cell 2. Each folder becomes one output
clip named after the folder. Full instructions, recording tips, and
troubleshooting are inside the notebook itself.

**Pipeline:** ElevenLabs line → record yourself mouthing along to it → this
notebook → lay the clean ElevenLabs audio under the clip in CapCut → if a mouth
is slightly off, run that clip through the FaceFusion notebook with just
`lip_syncer`.
