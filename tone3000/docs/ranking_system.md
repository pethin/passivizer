# Allomorph Storefront Voicing Ranking Architecture

This document defines the ranking and ordering system governing the 22 digital twin voicings in **Allomorph Tone Packs** on [Tone3000](https://tone3000.com).

---

## 1. Core Principles

The Allomorph ranking architecture is built on four fundamental tenets designed to maximize user engagement, storefront clarity, and musical value:

### 1.1 Inverse-Availability Principle (Native Tone Deprecation)
When a player browses or loads a tone pack for their physical bass, the primary value proposition is **transformational capacity**—giving the player sounds they **cannot** physically achieve with their stock instrument.
- **Rule:** Voicings that are already easily achieved from the player's physical base instrument must be assigned the **lowest instrument ranks** in the pack.
- **Example (P/J Bass):** A P/J bass natively possesses a Split-P neck pickup and a dual-pickup P/J blend. Consequently, the **Precision Bass Family** and **P/J Bass Family** are placed at the lowest instrument ranks (Ranks 14–20).
- **Example (Jazz Bass):** A Jazz bass natively possesses dual single-coils. Consequently, the native **Jazz Bass Family** is placed lower than the foreign Precision, P/J, and Music Man transformations.

### 1.2 Popularity & Transformative Demand Weighting
Among the non-native/transformative voicings, tones are ranked according to **real-world musical demand and recording ubiquity**:
- **Tier 1 (Universal Workhorses):** Jazz Bass dual-single scooped slap and active Sadowsky NYC 2-band; Music Man StingRay active parallel bite and series punch.
- **Tier 2 (Modern Boutique & Rock Legends):** Lakland/Sandberg P/MM active hybrids, Rickenbacker 4003 prog-rock clank with HPF, Dingwall multi-scale modern metal clank.
- **Tier 3 (Specialty & Historical Archetypes):** Gibson EB-0 Mudbucker ultra-low series humbucker.
- **Tier 4 (Acoustic Transducers):** Upright Acoustic Double Bass bridge force sensor simulation.

### 1.3 Strict Modular Topology Separation
Storefront categories must accurately reflect analog electrical topologies and physical coil arrangements. Arbitrary "catch-all" groupings are strictly forbidden:
- **Music Man StingRay Family:** Pure 2-band active dual-coil humbuckers placed at the bridge sweet spot are strictly isolated from hybrid models.
- **P/MM Modern Hybrids:** Compound dual-pickup configurations (Split-P neck + Music Man bridge) form their own dedicated hybrid category.
- **Progressive & Classic Rock Legends:** Historic and modern rock clank archetypes (Rickenbacker 4003, Dingwall, Gibson Mudbucker) are unified under a dedicated rock category.
- **Acoustic Transducers:** Piezo force sensor simulations are cleanly isolated from magnetic pickup guitars.

### 1.4 Terminal Utility Anchor
The final two positions (Ranks 21 and 22) in every pack are reserved for transparent calibration models:
- **Rank 21 (Modern Studio Active Buffer):** Demonstrates zero-cable-loading air band extension ($7.5\text{--}9.0\text{ kHz}$) on the user's physical pickups.
- **Rank 22 (Passive Character / True Bypass):** Bit-exact $0.00\text{ dB}$ reference for seamless A/B loudness and timbre benchmarking.

---

## 2. Edition-Specific Ranking Hierarchies

### 2.1 Standard P/J Bass & Mustang P/J Bass Editions
*Source Instrument:* Physical Split-P neck + Single-coil J bridge.  
*Native Tones:* Solo P-Bass (`[P-Bass]`) and P/J blend (`[Parallel]`).

| Rank Range | Sonic Family | Rationale / Musical Character |
| :--- | :--- | :--- |
| **01–05** | **Jazz Bass Family** | #1 most requested non-native sound. Reconstructs wide-aperture dual-single comb scoop and Sadowsky NYC 2-band slap that a split-coil neck cannot produce. |
| **06–07** | **Music Man StingRay Family** | High-demand active humbucker punch, hollow $2.5\text{ kHz}$ mid-scoop, and metallic clank unavailable on passive single/split coils. |
| **08–09** | **P/MM Modern Hybrids** | Modern boutique session tone (Sandberg California / Lakland 44-02) combining Split-P weight with Music Man bridge authority. |
| **10–12** | **Progressive & Classic Rock Legends** | Aggressive pick clank and sub-bass weight: Rickenbacker 4003 ($4.7\text{nF}$ HPF), Dingwall multi-scale ($7.3\text{ kHz}$ peak), and Gibson Mudbucker ($14.4\text{ H}$). |
| **13** | **Acoustic Transducers** | Bridge piezo force transducer on $41.5''$ upright scale with velocity-to-force leaky integration. |
| **14–18** | **Precision Bass & Tone Shaper Family** | *Base Instrument Solo Neck:* Calibrated deconvolution, ToneStyler notchless shunts, and flatwound damping. Lower rank because player already has a P-pickup. |
| **19–20** | **P/J Bass Family** | *Base Instrument Both Pickups:* Modern active buffer and vintage '80s passive P/J. Lowest instrument rank because player's bass already operates in this topology. |
| **21–22** | **Studio Buffers & Dynamics** | Studio $1\text{M}\Omega$ active buffer (cable deconvolution) and bit-exact $0.00\text{ dB}$ True Bypass baseline. |

---

### 2.2 Standard Jazz Bass Edition
*Source Instrument:* Dual single-coils in 60s spacing ($155.6\text{ mm}$ neck, $63.5\text{ mm}$ bridge).  
*Native Tones:* Solo J-neck, solo J-bridge, and dual J-pair parallel.

| Rank Range | Sonic Family | Rationale / Musical Character |
| :--- | :--- | :--- |
| **01–05** | **Precision Bass & Tone Shaper Family** | #1 most requested transformation for Jazz Bass players. Delivers high-inductance split-coil low-mid weight ($2.1\text{ kHz}$ peak) and ToneStyler flatwound Motown thump. |
| **06–07** | **Music Man StingRay Family** | Active 2-band parallel and series bridge humbucker punch, $2.5\text{ kHz}$ scoop, and signature metallic slap clank. |
| **08–09** | **P/J Bass Family** | Modern active and vintage '80s passive P/J configurations combining P-bass body with bridge single-coil cut. |
| **10–11** | **P/MM Modern Hybrids** | Split P + Music Man bridge dual-coil in parallel and series for modern boutique versatility and punch. |
| **12–14** | **Progressive & Classic Rock Legends** | Rickenbacker 4003 ($4.7\text{nF}$ HPF pick clank), Dingwall multi-scale ($7.3\text{ kHz}$ peak), and Gibson Mudbucker ($14.4\text{ H}$ subterranean boom). |
| **15** | **Acoustic Transducers** | Bridge piezo force sensor on $41.5''$ upright scale with velocity-to-force leaky integration. |
| **16–20** | **Jazz Bass Family** | *Base Instrument Profiles:* Re-EQed NYC active 2-band, vintage '60s harness, ToneStyler $22\text{nF}$, and Jaco decoupled growl. Lowest instrument rank because player already has Jazz pickups. |
| **21–22** | **Studio Buffers & Dynamics** | Studio $1\text{M}\Omega$ active buffer and bit-exact $0.00\text{ dB}$ True Bypass baseline. |

---

### 2.3 Standard Precision Bass Edition
*Source Instrument:* Single split-coil P-Bass centered at $125.0\text{ mm}$.  
*Native Tones:* Solo P-Bass.

| Rank Range | Sonic Family | Rationale / Musical Character |
| :--- | :--- | :--- |
| **01–05** | **Jazz Bass Family** | Top transformative capability: converts a single split-coil into dual-aperture 60s single-coils with wideband slap sparkle and Jaco bridge growl. |
| **06–07** | **Music Man StingRay Family** | Active 2-band parallel and series bridge humbucker clank and punch. |
| **08–09** | **P/J Bass Family** | Modern active and vintage '80s passive P/J combinations providing dual-pickup growl and articulation. |
| **10–11** | **P/MM Modern Hybrids** | Split P + Music Man bridge dual-coil in parallel and series for modern boutique versatility and punch. |
| **12–14** | **Progressive & Classic Rock Legends** | Rickenbacker 4003 ($4.7\text{nF}$ HPF), Dingwall multi-scale ($7.3\text{ kHz}$ peak), and Gibson Mudbucker ($14.4\text{ H}$). |
| **15** | **Acoustic Transducers** | Bridge piezo force sensor on $41.5''$ upright scale with velocity-to-force leaky integration. |
| **16–20** | **Precision Bass & Tone Shaper Family** | *Base Instrument Profiles:* Vintage '62 CTS, Modern Ceramic 500k, and ToneStyler shunts ($22\text{nF}$, $47\text{nF}$, $100\text{nF}$). Lowest instrument rank because player already owns a P-Bass. |
| **21–22** | **Studio Buffers & Dynamics** | Studio $1\text{M}\Omega$ active buffer and bit-exact $0.00\text{ dB}$ True Bypass baseline. |

---

### 2.4 Active Soapbar Bass Edition
*Source Instrument:* Modern 34" active bass with dual blade soapbars ($135.0\text{ mm}$ neck, $55.0\text{ mm}$ bridge) and 3-band active EQ buffer.  
*Native Tones:* Modern active dual-blade humbuckers with blend control.

| Rank Range | Sonic Family | Rationale / Musical Character |
| :--- | :--- | :--- |
| **01–05** | **Precision Bass & Tone Shaper Family** | #1 most requested transformation for active soapbar players. Replaces modern sterile active tone with warm, organic, woody Alnico V split-coil body ($2.1\text{ kHz}$ peak) and ToneStyler flatwound Motown thump. |
| **06–10** | **Jazz Bass Family** | Delivers the airy, open, dynamic breath of vintage 1960s dual single-coils ($1\text{ kHz}$ phase-cancellation scoop and Jaco decoupled bridge growl) that wide dual-blade soapbars cannot natively produce. |
| **11–12** | **Music Man StingRay Family** | Aggressive sweet-spot humbucker clank, $2.5\text{ kHz}$ hollow mid-scoop, and series bark. |
| **13–14** | **P/MM Modern Hybrids** | Sandberg California / Lakland 44-02 style Split-P + Music Man parallel and series authority. |
| **15–17** | **Progressive & Classic Rock Legends** | Rickenbacker 4003 ($4.7\text{nF}$ HPF pick clank), Dingwall multi-scale ($7.3\text{ kHz}$ sparkle), and Gibson Mudbucker ($14.4\text{ H}$ sub-bass). |
| **18** | **Acoustic Transducers** | Bridge piezo force sensor on $41.5''$ upright scale with velocity-to-force leaky integration. |
| **19–20** | **P/J Bass Family** | Modern active and vintage '80s passive P/J configurations. Lowest rank among non-native combinations due to topology proximity to dual active pickups. |
| **21–22** | **Studio Buffers & Dynamics** | Studio $1\text{M}\Omega$ active buffer and bit-exact $0.00\text{ dB}$ True Bypass baseline. |

---

### 2.5 Active StingRay Bass Edition
*Source Instrument:* 34" active Music Man StingRay / Sterling Ray34 with single bridge sweet-spot dual-coil humbucker ($66.0\text{ mm}$) and active 2-band preamp.  
*Native Tones:* Music Man StingRay Active 2-Band Parallel (1:1 physical & electrical identity twin!) and Series.

| Rank Range | Sonic Family | Rationale / Musical Character |
| :--- | :--- | :--- |
| **01–05** | **Precision Bass & Tone Shaper Family** | #1 missing sound for StingRay players. Delivers the warm, woody, low-mid thump of a neck split-coil ($125\text{ mm}$) and flatwound Motown thump that a bridge humbucker physically lacks. |
| **06–10** | **Jazz Bass Family** | Dual single-coil wide-aperture $1\text{ kHz}$ comb scoop, Marcus Miller slap sparkle, and Jaco bridge bite. |
| **11–12** | **P/MM Modern Hybrids** | Combines virtual P-neck with the player's physical StingRay bridge humbucker in parallel and series. |
| **13–14** | **P/J Bass Family** | Modern active and vintage '80s passive P/J configurations combining P-neck weight with bridge clarity. |
| **15–17** | **Progressive & Classic Rock Legends** | Rickenbacker 4003 ($4.7\text{nF}$ HPF pick clank), Dingwall multi-scale ($7.3\text{ kHz}$ peak), and Gibson Mudbucker ($14.4\text{ H}$ subterranean boom). |
| **18** | **Acoustic Transducers** | Bridge piezo force sensor on $41.5''$ upright scale with velocity-to-force leaky integration. |
| **19–20** | **Music Man StingRay Family** | *Base Instrument Profiles:* Active 2-Band Parallel (bit-exact $0.00\text{ dB}$ identity match) and Active 2-Band Series bark. Relegated to lowest instrument ranks per the inverse-availability principle. |
| **21–22** | **Studio Buffers & Dynamics** | Studio $1\text{M}\Omega$ active buffer and bit-exact $0.00\text{ dB}$ True Bypass baseline. |

---

## 3. Governance & Quality Checklist

When modifying or generating new Tone3000 pack listings:
1. **Verify Rank Inversion:** Ensure native pickup configurations sit in the lower half of the listing (Ranks 14–20 for native pickup architectures).
2. **Verify Distinct Families:** Confirm StingRay is never merged with P/J, and P/MM is never merged with Acoustic Transducers.
3. **Check Character Limits:** Ensure the total listing length remains between 7,500 and 9,600 characters ($\le 10,000$ max).
4. **Preserve Bracketed Tags:** Every multi-pickup listing must contain `[Parallel]`, `[Center]`, `[Neck]`, `[Bridge]`, `[P-Bass]`, or `[J-Bridge]` tags.
5. **Active Calibration Integrity:** Active editions must direct players to set onboard active EQs flat at center detents.
