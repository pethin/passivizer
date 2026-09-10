# Tone3000 Tone Pack Catalog

This directory contains the standardized storefront product descriptions for **Allomorph Tone Packs** on [Tone3000](https://tone3000.com), engineered for Neural Amp Modeler (NAM) and the Darkglass Anagram pedalboard.

Each pack contains 22 precision digital twin voicings calibrated via true differential circuit deconvolution ($H_{\text{diff}} = H_{\text{tgt}} / H_{\text{src}}$) to transform a specific physical bass guitar into iconic vintage, modern active, heavy multi-scale, and acoustic bass topologies.

---

## Pack Catalog & Storefront Listings

| Pack Edition | Source Instrument Calibration | Recommended Knobs / Switches | Profile Document | Production Artwork (SVG / JPG) |
| :--- | :--- | :--- | :--- | :--- |
| **Standard Precision Bass Edition** | 34" Standard Fender P-Bass (Passive Split-P) | Vol 100%, Tone 100% | [`standard_precision_bass.txt`](standard_precision_bass.txt) | [`allomorph_standard_precision_bass.svg`](../assets/allomorph_standard_precision_bass.svg) &bull; [JPG](../assets/allomorph_standard_precision_bass.jpg) |
| **Standard Jazz Bass Edition** | 34" Standard Fender Jazz Bass (Passive Single-Coil Pair) | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[Neck]`, `[Bridge]` | [`standard_jazz_bass.txt`](standard_jazz_bass.txt) | [`allomorph_standard_jazz_bass.svg`](../assets/allomorph_standard_jazz_bass.svg) &bull; [JPG](../assets/allomorph_standard_jazz_bass.jpg) |
| **Standard P/J Bass Edition** | 34" Standard Fender P/J Bass (Split-P Neck + J Bridge) | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[P-Bass]`, `[J-Bridge]` | [`standard_pj_bass.txt`](standard_pj_bass.txt) | [`allomorph_standard_pj_bass.svg`](../assets/allomorph_standard_pj_bass.svg) &bull; [JPG](../assets/allomorph_standard_pj_bass.jpg) |
| **Mustang P/J Bass Edition** | 30" Short-Scale Fender Mustang P/J Bass | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[P-Bass]`, `[J-Bridge]` | [`mustang_pj_bass.txt`](mustang_pj_bass.txt) | [`allomorph_mustang_pj_bass.svg`](../assets/allomorph_mustang_pj_bass.svg) &bull; [JPG](../assets/allomorph_mustang_pj_bass.jpg) |
| **Active Soapbar Bass Edition** | 34" Modern Active Dual-Soapbar Bass (Ibanez SR / Yamaha TRBX / Schecter) | Vol 100%, Active EQ Flat (Center Detents), Blend configs: `[Center]`, `[Neck]`, `[Bridge]` | [`active_soapbar_bass.txt`](active_soapbar_bass.txt) | [`allomorph_active_soapbar_bass.svg`](../assets/allomorph_active_soapbar_bass.svg) &bull; [JPG](../assets/allomorph_active_soapbar_bass.jpg) |
| **Active StingRay Bass Edition** | 34" Active Music Man StingRay / Sterling Ray34 (Bridge MM Humbucker) | Vol 100%, Active EQ Flat (Center Detents) | [`active_stingray_bass.txt`](active_stingray_bass.txt) | [`allomorph_active_stingray_bass.svg`](../assets/allomorph_active_stingray_bass.svg) &bull; [JPG](../assets/allomorph_active_stingray_bass.jpg) |

---

## Storefront Engineering Constraints

All pack descriptions in this directory strictly adhere to Tone3000 platform guidelines:
1. **Character Limit Compliance:** Tone3000 enforces a strict maximum length of 10,000 characters per listing. All 6 packs are calibrated between 7,500 and 9,600 characters.
2. **Pickup Configuration Tags:** Multi-pickup editions (Jazz, P/J, Mustang P/J) include bracketed physical selector tags on every voicing (e.g. `[Parallel]`, `[Neck]`, `[Bridge]`, `[P-Bass]`, `[J-Bridge]`) so users know exactly how to set their instrument switches for optimal acoustic cancellation matching.
3. **Concise Voicing Summaries:** Each of the 22 target voicings is distilled into 1–2 punchy, informative sentences highlighting the resonant peak ($f_r$), pot loading, and physical sonic character.
4. **Independent Legal Disclaimers:** Trademark disclaimers and non-commercial/commercial user rights are explicitly codified per listing.
5. **Inverse-Availability Voicing Ranking:** Packs are ordered by user utility and transformative value. Voicings that cannot be natively produced by the player's physical instrument sit near the top; native base-instrument voicings are relegated to the lowest ranks (see [`ranking_system.md`](ranking_system.md)).

---

## Digital Twin Voice Architecture & Ranking

Every pack provides comprehensive coverage across eight modular sonic families, ordered according to the [Tone Ranking Architecture](ranking_system.md):

1. **Jazz Bass Family:**
   - Modern Active Jazz Bass (NYC 2-Band Preamp with Cable Isolation)
   - Vintage '60s Jazz Bass Pair (Dual Parallel 250k Harness with 1 kHz Scoop)
   - '60s Jazz Bass Pair (22nF ToneStyler Vocal Mid Bump @ 762 Hz)
   - '60s Jazz Bridge Growl (Jaco Bias 55k Wiper Decoupling)
   - '60s Jazz Bridge Single-Coil (Articulate 63.5mm Datum Punch)
2. **Music Man StingRay Family:**
   - Music Man StingRay Active 2-Band Parallel (Classic Hollow Mid-Scoop & Clank)
   - Music Man StingRay Active 2-Band Series (Aggressive 2.1 kHz Bark & +2.5 dB EMF)
3. **P/MM Modern Hybrids:**
   - Modern Active P/MM Bass (Sandberg/Lakland Parallel Split + MM Sweet Spot)
   - P/MM Hybrid Series Sum (Massive 7.2H Inductive Surge & +5.8 dB Punch)
4. **Progressive & Classic Rock Legends:**
   - Rickenbacker 4003 Bridge (Vintage 4.7nF Series HPF Clank)
   - Dingwall Fanned Multi-Scale Bridge (34"–37" High Wave-Speed Sparkle @ 7.3 kHz)
   - Gibson Mudbucker Ultra Series (14.4H Neck-Heel Sidewinder Sub-Bass)
5. **Acoustic Transducers:**
   - Upright Acoustic Double Bass (Underwood/Realist Bridge Force Sensor with Leaky Integration)
6. **Precision Bass & Tone Shaper Family:**
   - Vintage '62 P-Bass (Alnico V - Tone Open CTS 250k)
   - Modern Ceramic Split-P (Boutique 500k with Hybrid Treble Bleed)
   - Vintage '62 Split-P (22nF ToneStyler Punch @ 440 Hz)
   - Vintage '62 Split-P Motown Thump (47nF ToneStyler Flatwound Damping)
   - Vintage '50s Split-P Deep Dub (100nF ToneStyler Fullerton 0.1µF Spec)
7. **P/J Bass Family:**
   - Modern Active P/J Bass (Active 2-Band Boost @ 40 Hz & 4 kHz)
   - Vintage '80s Passive P/J Bass (Duff McKagan / BB3000 Parallel Sum)
8. **Studio Buffers & Dynamics:**
   - Modern Studio Active Buffer (Zero Cable Loading / 1M Impedance Twin @ 7.5–9.0 kHz)
   - Passive Character (Bit-Exact 0.00 dB True Bypass Linear Baseline)

---

## Recommended Darkglass Anagram Signal Flow

```
[Physical Bass]
      │  (Volume 100%, Tone 100%)
      ▼
[Block 1: Allomorph NAM Preamp]  ◄── Tone3000 Pickup Twin
      │  (Impedance matching, coil deconvolution, aperture reshaping)
      ▼
[Block 2: Preamp / Overdrive]   ◄── Microtubes B7K, Vintage Ultra, SVT, etc.
      │  (Distorts authentic pickup resonance peaks)
      ▼
[Block 3: Cab IR Loader]        ◄── 8x10, 4x10, 1x15 Speaker Cab Impulse
      │
      ▼
[FOH / Interface / DAW]
```
