# Magnetic Aperture & Spatial Comb-Filtering Math

This document details the spatial, mechanical, and string-vibration physics modeled in **Passivizer** to recreate physical pickup geometry.

---

## 1. Magnetic Aperture Width ($w$)

A magnetic pickup does not sample the vibrating string at an infinitesimal point. Instead, its permanent magnets and pole pieces create a sensing field with a finite spatial aperture $w$ along the string's axis.

```
                  ◄────── w ──────►
                  ┌───────────────┐
String: ══════════│═══════════════│═══════════
                  └───────────────┘
                     Pickup Pole
```

### The Sinc Comb-Filter Effect
Because the pickup integrates string motion across width $w$, wavelengths shorter than $w$ cancel out across the pole. In the frequency domain, assuming a string wave speed $v$, the transfer function is modeled by the unnormalized sinc function:

$$H_{\text{aperture}}(f) = \left| \frac{\sin\left(\frac{\pi f w}{v}\right)}{\frac{\pi f w}{v}} \right| = \left| \text{sinc}\left( \frac{f \cdot w}{v} \right) \right|$$

#### First Aperture Null:
$$f_{\text{null}} = \frac{v}{w}$$

* **Narrow Aperture (Jazz Bass single-coil, $w \approx 0.75''$):** The first null sits higher up in the frequency spectrum, preserving harmonic transients, "snap," and pick attack.
* **Wide Aperture (Precision Bass / Music Man, $w \approx 1.00''\text{ to }1.50''$):** The null pulls down into the upper treble ($4\text{--}6\text{ kHz}$), creating a naturally warmer, thicker, low-pass characteristic.

---

## 2. Multi-String Wave Speed Problem & The Passivizer Solution

In simple scripts like `precifier`, wave speed is assumed constant based on the open E string:
$$v_E = 2 \cdot L \cdot f_0 = 2 \cdot (34 \times 0.0254) \cdot 41.20 \approx 71.07\text{ m/s}$$

### The Multi-String Reality
Wave speed is governed by string tension ($T$) and linear mass density ($\mu$):
$$v = \sqrt{\frac{T}{\mu}} = 2 \cdot L \cdot f_{\text{open}}$$

For a standard 34" 4-string bass (standard gauge .045 – .105):

| String | Open Frequency ($f_0$) | Wave Speed ($v$) | Aperture Null ($w=1.0''$) |
| :--- | :--- | :--- | :--- |
| **E1** | $41.20\text{ Hz}$ | $71.07\text{ m/s}$ | $2,798\text{ Hz}$ |
| **A1** | $55.00\text{ Hz}$ | $94.93\text{ m/s}$ | $3,737\text{ Hz}$ |
| **D2** | $73.42\text{ Hz}$ | $126.73\text{ m/s}$ | $4,989\text{ Hz}$ |
| **G2** | $98.00\text{ Hz}$ | $169.15\text{ m/s}$ | $6,659\text{ Hz}$ |
| *(Low B)* | $30.87\text{ Hz}$ | $53.28\text{ m/s}$ | $2,098\text{ Hz}$ |

> [!WARNING]
> If an IR uses a single wave speed ($v_E = 71\text{ m/s}$), it forces a deep notch at $2.8\text{ kHz}$. While correct for the open E string, this creates an artificial, hollow notch on the D and G strings where the real notch is well above $5\text{ kHz}$.

### The Passivizer Composite Aperture Solution
Passivizer integrates the aperture response across the operational wave speeds of all four (or five) strings, weighting typical playing zones:

$$H_{\text{composite}}(f) = \frac{1}{\sum k_i} \sum_{i \in \{\text{E,A,D,G}\}} k_i \cdot \left| \text{sinc}\left(\frac{f \cdot w}{v_i}\right) \right| + \text{floor}$$

This smooths out localized notches while preserving the authentic, broad high-frequency aperture rolloff across the entire instrument.

---

## 3. Dual-Coil Humbucker Spatial Comb-Filtering ($d$)

In multi-coil pickups such as the **Bartolini MM42CBJD3 quad-coil** or vintage StingRay humbuckers, two coil centers are separated by distance $d$ along the string (typically $d \approx 0.75'' = 19.05\text{ mm}$):

```
        Coil 1 (Front)      Coil 2 (Rear)
             ┌───┐               ┌───┐
String: ═════│═══│═══════════════│═══│═════
             └───┘               └───┘
               ◄──────── d ───────►
```

When connected in phase (whether Parallel or Series), the summed signal exhibits spatial comb filtering:

$$H_{\text{comb}}(f) = \left| \cos\left( \frac{\pi f d}{v} \right) \right|$$

#### First Humbucker Notch:
$$f_{\text{notch}} = \frac{v}{2d}$$

For $d = 0.75''$ ($0.01905\text{ m}$) at average wave speed $v \approx 95\text{ m/s}$:
$$f_{\text{notch}} \approx \frac{95}{2 \times 0.01905} \approx 2,493\text{ Hz}$$

This spatial notch around $2.5\text{ kHz}$ is the acoustic fingerprint of a Music Man humbucker—it creates the mid-scoop that gives the StingRay its open, aggressive "growl" and slap clarity.

---

## 4. Scale-Length Transformation & Multi-Scale Physics (30"/32" $\to$ 34" / 37")

When translating a **30" short-scale** or **32" medium-scale** source bass into standard **34"** or **34"–37" multi-scale (Dingwall-style)** tones, Passivizer models three physical phenomena:

### A. Wave-Speed Scaling Ratio ($\kappa_v$)
Wave speed scales directly with vibrating length for any given pitch:
$$\kappa_v = \frac{L_{\text{target}}}{L_{\text{source}}}$$

* **30" to 34" Conversion:** $\kappa_v = \frac{34}{30} = 1.133\ (+13.3\%)$
* **32" to 34" Conversion:** $\kappa_v = \frac{34}{32} = 1.0625\ (+6.25\%)$
* **30" to 37" Multi-Scale Conversion:** $\kappa_v = \frac{37}{30} = 1.233\ (+23.3\%)$

As wave speed increases, the physical aperture and comb-filter null frequencies shift upward:
$$f_{\text{null, target}} = f_{\text{null, source}} \cdot \kappa_v$$
This lifts the frequency ceiling of the pickup, extending harmonic transient definition and high-register "snap."

### B. String Tension & Low-Mid De-Mudding ($H_{\text{tension}}$)
Short-scale (30") and medium-scale (32") instruments have lower string tension, which produces:
1. Higher mechanical displacement at the fundamental (warm, loose "tubby" bloom in the $180\text{--}250\text{ Hz}$ range).
2. Slightly softer high-harmonic transient attack.

In contrast, full-scale 34" and 37" multi-scale basses exhibit massive tension ($\sim 42\text{--}48\text{ lbs}$ on low B/E strings), producing:
* **Laser-tight, piano-like sub-bass** ($40\text{--}80\text{ Hz}$).
* **Controlled, clean low-mids** without muddiness.
* **Aggressive, percussive metallic clank** ($2.5\text{--}3.8\text{ kHz}$) that stays coherent under heavy Darkglass drive engines.

Passivizer models this acoustic transformation with a multi-band tension transfer filter:
* **For 34" Conversion:** $-2.0\text{ dB}$ dip @ $210\text{ Hz}$ ($Q=1.2$) $+$ $+1.8\text{ dB}$ high shelf @ $2.8\text{ kHz}$.
* **For Multi-Scale (Dingwall) Conversion:** $+1.5\text{ dB}$ sub focus @ $75\text{ Hz}$, $-3.5\text{ dB}$ de-mud @ $220\text{ Hz}$, $+3.5\text{ dB}$ metallic clank peak @ $3.2\text{ kHz}$, and $+2.0\text{ dB}$ top-end air @ $5\text{ kHz}$.

### C. Angled Multi-Scale Pickup Geometry
On fanned-fret instruments like the Dingwall NG2/NG3, pickups are mounted parallel to the fanned bridge saddles. This ensures that the sensing point relative to the scale line ($x / L$) remains uniform across all strings, eliminating the flubby low-end of straight pickups on low B and E strings while maintaining smooth treble on the G string. Passivizer compensates for this geometric alignment across string channels.

