# Tone3000 Tone Pack Catalog

This directory contains the standardized storefront product descriptions for **Allomorph Tone Packs** on [Tone3000](https://tone3000.com), engineered for Neural Amp Modeler (NAM) and the Darkglass Anagram pedalboard.

Each pack contains 22 precision digital twin voicings calibrated via true differential circuit deconvolution ($H_{\text{diff}} = H_{\text{tgt}} / H_{\text{src}}$) to transform a specific physical bass guitar into iconic vintage, modern active, heavy multi-scale, and acoustic bass topologies.

---

## Pack Catalog & Storefront Listings

| Pack Edition | Source Instrument Calibration | Recommended Knobs / Switches | Profile Document | Production Artwork (SVG / JPG) |
| :--- | :--- | :--- | :--- | :--- |
| **Standard Precision Bass Edition** | 34" Standard Fender P-Bass (Passive Split-P) | Vol 100%, Tone 100% | [`standard_precision_bass.md`](standard_precision_bass.md) | [`allomorph_standard_precision_bass.svg`](../assets/allomorph_standard_precision_bass.svg) &bull; [JPG](../assets/allomorph_standard_precision_bass.jpg) |
| **Standard Jazz Bass Edition** | 34" Standard Fender Jazz Bass (Passive Single-Coil Pair) | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[Neck]`, `[Bridge]` | [`standard_jazz_bass.md`](standard_jazz_bass.md) | [`allomorph_standard_jazz_bass.svg`](../assets/allomorph_standard_jazz_bass.svg) &bull; [JPG](../assets/allomorph_standard_jazz_bass.jpg) |
| **Standard P/J Bass Edition** | 34" Standard Fender P/J Bass (Split-P Neck + J Bridge) | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[P-Bass]`, `[J-Bridge]` | [`standard_pj_bass.md`](standard_pj_bass.md) | [`allomorph_standard_pj_bass.svg`](../assets/allomorph_standard_pj_bass.svg) &bull; [JPG](../assets/allomorph_standard_pj_bass.jpg) |
| **Mustang P/J Bass Edition** | 30" Short-Scale Fender Mustang P/J Bass | Vol 100%, Tone 100%, Pickup configs: `[Parallel]`, `[P-Bass]`, `[J-Bridge]` | [`mustang_pj_bass.md`](mustang_pj_bass.md) | [`allomorph_mustang_pj_bass.svg`](../assets/allomorph_mustang_pj_bass.svg) &bull; [JPG](../assets/allomorph_mustang_pj_bass.jpg) |

---

## Storefront Engineering Constraints

All pack descriptions in this directory strictly adhere to Tone3000 platform guidelines:
1. **Character Limit Compliance:** Tone3000 enforces a strict maximum length of 10,000 characters per listing. All 4 packs are calibrated between 7,500 and 9,600 characters.
2. **Pickup Configuration Tags:** Multi-pickup editions (Jazz, P/J, Mustang P/J) include bracketed physical selector tags on every voicing (e.g. `[Parallel]`, `[Neck]`, `[Bridge]`, `[P-Bass]`, `[J-Bridge]`) so users know exactly how to set their instrument switches for optimal acoustic cancellation matching.
3. **Concise Voicing Summaries:** Each of the 22 target voicings is distilled into 1–2 punchy, informative sentences highlighting the resonant peak ($f_r$), pot loading, and physical sonic character.
4. **Independent Legal Disclaimers:** Trademark disclaimers and non-commercial/commercial user rights are explicitly codified per listing.

---

## Digital Twin Voice Architecture (22 Voicings)

Every pack provides identical high-resolution digital twin coverage spanning seven sonic families:

1. **Jazz Bass Family (01–04):**
   - Modern Active Jazz Bass (NYC 2-Band Preamp)
   - 1962 Stack-Knob Jazz Bass (Dual Concentric 250k/500k)
   - 1975 Marcus Jazz Bass (Ash/Maple 70s Bridge Spacing)
   - Jaco Pastorius 1962 Fretless Jazz (Bridge Solo)
2. **Precision & Mustang Family (05–08):**
   - 1963 Motown Precision Bass (Flatwound Jamerson P-Bass)
   - 1951 Early Precision "Tele" Bass (Single-Coil Bakelite Bobbin)
   - 1970s Classic Precision Bass (Punchy Rock Fingerstyle & Pick)
   - 1966 Mustang Short-Scale Bass (Direct 30" Split-Coil Thump)
3. **Music Man Family (09–12):**
   - 1976 Music Man StingRay (Alnico V 2-Band Preamp @ 3.4 kHz)
   - Modern StingRay Special 4H (Neodymium 18V 3-Band Preamp)
   - Modern Active P/MM Hybrid (Lakland/Sandberg Parallel Bridge Sweet Spot)
   - High-Output P/MM Hybrid Series (7.2H High-Inductance Punch)
   - Music Man Sterling (Ceramic Parallel Snarl)
4. **Specialty & Vintage Voicings (14–16):**
   - 1968 Rickenbacker 4001S (Horseshoe & Hi-Gain Bridge with 0.0047uF Cap)
   - Gibson EB-0 / EB-3 "Mudbucker" (30H Sidewinder Ultra Series Sub-Bass)
   - Modern Humbucker Soapbar (Boutique Bartolini Deep Growl)
5. **ToneStyler Notchless Shunts (17–18):**
   - ToneStyler Notchless Rolloff #8 (1.5 kHz Mid-Punch)
   - ToneStyler Notchless Rolloff #12 (400 Hz Warm Sub-Bass)
6. **Heavy Rock & Acoustic Transducers (19–20):**
   - Dingwall Fanned Multi-Scale Bridge (34"–37" High Wave-Speed Clank @ 7.3 kHz)
   - Upright Acoustic Double Bass (Underwood/Realist Bridge Force Transducer)
7. **Studio Buffers & Unity Baselines (21–22):**
   - Modern Studio Active Buffer (Zero Cable Loading / 1M Impedance Twin)
   - Passive Character (Bit-Exact 0.00 dB True Bypass Reference)

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
