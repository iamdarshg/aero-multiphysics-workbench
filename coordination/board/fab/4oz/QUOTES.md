# Verbatim vendor rows — 4 oz capability (fetched 2026-11-15)

All quotes are copied from the vendor's own page text as returned to `web_fetch`. No secondary
sources (no blogs, no calculators, no forum posts) are used anywhere in this unit.

---

## 1. PCBWay — Heavy Copper PCBs (capability table)

URL: https://www.pcbway.com/pcb_prototype/Thick_Copper_PCBs.html

> | **Min.Track/Spacing** | For External layers:
> 4oz Cu 13mil/13mil, 5oz Cu 18mil/18mil
> 6oz Cu 18mil/18mil, 12oz Cu 20mil/32mil
> | For Internal layers:
> 4oz Cu 13mil/13mil, 5oz Cu 18mil/18mil
> 6oz Cu 18mil/18mil, 12oz Cu 20mil/32mil |
> | **Min.Hole Size** | 10mil |
> | **Max Outer Layer Copper Weight(Finished)** | 15oz |
> | **Max Inner Layer Copper Weight** | 12oz |

13 mil = 0.3302 mm. **4 oz: 0.330 mm trace / 0.330 mm space, outer AND inner.**

Annular ring (generic standard-capability table, NOT split by copper weight):
URL: https://www.pcbway.com/capabilities.html

> | **Min Width of Annular Ring** | 0.15mm(6mil) | For pads with vias in the middle, Min width for
> Annular Ring is 0.15mm(6mil). |

> | Outer Layer Copper Thickness | 1oz/2oz/3oz/4oz/5oz/6oz/7oz/8oz
> (35um/70um/105um/140um/175um/210um/245um/280um) |

Note the contradiction inside PCBWay's own site: the standard table advertises 0.1 mm min trace and
0.15 mm ring across the whole 1–8 oz range, while the heavy-copper table that actually carries a
4 oz row says 13/13 mil. The heavy-copper row is the specific one and wins; the generic numbers are
1–2 oz behaviour.

---

## 2. Multi Circuit Boards (Multi-CB, Germany) — Conductor / Copper thickness

URL: https://www.multi-circuit-boards.eu/en/pcb-design-aid/surface/conductor-copper-thickness.html

Table header: "Copper thickness Outer* and Inner layers | **Standard** Min. conductor trace width |
-space | annular ring | **Special production** Min. conductor trace width | -space | annular ring"

> | 70µm | 150µm | 150µm | 150µm | 150µm | 150µm | 130µm |
> | 105µm | 225µm | 225µm | 225µm | 200µm | 200µm | 170µm |
> | **140µm | 300µm | 300µm | 300µm | 250µm | 250µm | 200µm** |
> | 175µm | 400µm | 400µm | 400µm | 280µm | 280µm | 240µm |

Also, on the same page: "In the favourable pool service for 4 layers, either 18µm or 35µm copper is
possible on the inner layers."

**140 µm (4 oz): 0.300/0.300/0.300 standard; 0.250/0.250/0.200 in special production.** 4 oz is
not a pool-service option at all.

---

## 3. Bay Area Circuits — PCB Capabilities ("Trace / Space" block)

URL: https://bayareacircuits.com/pcb-capabilities/
PDF mirror: https://bayareacircuits.com/wp-content/uploads/2025/12/capabilities.pdf

> | **Outer Layers (finished copper)** | 1 oz Cu Min Trace/Space .004″ | 1 oz Cu Min Trace/Space .002″ |
> | 2 oz Cu Min Trace/Space .006″ | 2 oz Cu Min Trace/Space .005″ |
> | 3 oz Cu Min Trace/Space .008″ | 3 oz Cu Min Trace/Space .008″ |
> | **4 oz Cu Min Trace/Space .012″** | **4 oz Cu Min Trace .011″ Space .012″** |
> | | 5 oz Cu Min Trace/Space .016″ |

And, in the overview block on the same page:

> | **Annular Ring** | 0.005″ At drilled size, class 2 | 0.003″ Mechanical, 0.001″ Laser |
> | **Outer Layers Finished Copper** | 1 oz to 2 oz | 1 oz to 5 oz |

**4 oz: 0.305/0.305 mm standard, 0.279/0.305 mm advanced. Ring 0.127 mm — but the ring line is not
indexed to copper weight, so it is not 4 oz evidence.**

---

## 4. LeitOn (Leiton GmbH, Berlin) — Design rules, rigid boards

URL: https://www.leiton.de/technologie-starre-leiterplatten.html
(section "Kupferlagen (außen) - starre Leiterplatten", columns "Onlinekalkulation/Standard" vs
"auf explizite Anfrage" = only on explicit request)

> | Kleinste Leiterbahn 105µm | 0,25mm | 0,20mm |
> | **Kleinste Leiterbahn 140µm | nicht möglich | 0,30mm** |
> | Kleinste Leiterbahn 210µm | nicht möglich | 0,60mm |
> | Kleinster Leiterbahnabstand 105µm | 0,25mm | 0,20mm |
> | **Kleinster Leiterbahnabstand 140µm | nicht möglich | 0,40mm** |
> | Kleinster Leiterbahnabstand 210µm | nicht möglich | 0,60mm |
> | Kleinster Restring 105µm | 0,20mm | 0,15mm |
> | **Kleinster Restring 140µm | nicht möglich | 0,25mm** |
> | Kleinster Restring 210µm | nicht möglich | 0,30mm |

**140 µm (4 oz), outer: track 0.30 mm / space 0.40 mm / annular ring 0.25 mm — and only "auf
explizite Anfrage". Not orderable through their online calculator at all.**

This is the single most decisive row in the whole unit: at 4 oz LeitOn needs a **0.40 mm space**,
exactly 2× the ESC's 0.200 mm.

---

## 5. Advanced Circuits / AdvancedPCB — Manufacturing Capabilities

URL: https://www.advancedpcb.com/en-us/resources/manufacturing-capabilities/
(columns: Standard | Advanced | Development (NPI); values in inches)

> | Inner Layer Width - 3 oz. Cu | 0.008 | 0.0075 | 0.006 |
> | Inner Layer Width - 4 oz. Cu | 0.01 | 0.009 | N/A |
> ...
> | Outer Layer Width - 2 oz. Cu. Base | 0.007 | 0.0055 | 0.004 |
> | Outer Layer Width - 3 oz. Cu. Base | 0.009 | 0.0075 | 0.006 |
> | Outer Layer Space - Trace to Trace - 3 oz. Cu. Base | 0.009 | 0.0075 | 0.006 |

**Evidence of absence: the outer-layer block stops at 3 oz.** There is no "Outer Layer Width - 4 oz"
row and no "Outer Layer Space - 4 oz" row anywhere in the table; 4 oz appears only as an *inner*
layer (0.010″ = 0.254 mm, with the advanced column "N/A"). So 4 oz outer copper is not a published
capability at Advanced Circuits, and their **3 oz outer floor is 0.009″ = 0.229 mm** already.

---

## 6. JLCPCB — Copper Weight (Thickness) Guide (help article, updated 2026-11-10)

URL: https://jlcpcb.com/help/article/jlcpcb-copper-weight

> | FR4 PCB | Outer layer | 1oz, 2oz (standard) | Heavier options for 2-layer only |
> | | 2-layer FR4 only | 2.5oz, 3.5oz, 4.5oz | Special high-current designs |
> | | Inner layer | 0.5oz (default), 1oz, 2oz | ... |

> | Copper Weight | Applicable PCB Type | Min. Trace Width / Space |
> | 2oz | Any layer FR4 | 0.16 mm (6.5 mil) |
> | 2.5oz | 2-layer FR4 | 0.20 mm (8 mil) |
> | 3.5oz | 2-layer FR4 | 0.25 mm (10 mil) |
> | 4.5oz | 2-layer FR4 | 0.30 mm (12 mil) |

**Evidence of absence for this board: the ESC is 4-layer, and JLC's heavy weights are 2-layer FR4
only. There is no 4 oz row at all**; the nearest is 4.5 oz at 0.30 mm. On a 4-layer board JLC stops
at 2 oz, where the floor is 0.16 mm — which is the one number in this whole unit that is *below*
0.200 mm.

---

## 7. Eurocircuits — Classification table (primary source image, table dated 07/05/2024)

Page: https://www.eurocircuits.com/technical-guidelines/pcb-design-guidelines/classification/
Table image: https://www.eurocircuits.com/content/uploads/2025/04/EC-classification-ENGLISH-5-2024-V3.png
Local copy read for this unit: `evidence/fab-esc-4oz/sources/EC-classification-ENGLISH-5-2024-V3.png`
(sha256 47c81c3d60cbf94f46bd0f5c1d70e9a90dfe50342da3be849f4421d47c962080)

Block "Base Cu OL" (outer layer, min Pattern Values):

> | Base Cu OL | OTT-OTP-OPP | OTW |
> | 12µm | 0.090 | 0.090 |
> | 18µm | 0.100 | 0.100 |
> | 35µm 1oz | 0.125 | 0.125 |
> | 70µm 2oz | 0.200 | 0.200 |
> | **105µm 3oz | 0.250 | 0.250** |

And from the page text, the governing rule:

> "The thickness of the starting copper foil determines the minimum pattern values that are possible.
> This means that the highest pattern class possible depends on the copper thicknesses."
> "Not all copper thicknesses are available in all services."

**Evidence of absence: the outer-layer copper column ends at 105 µm (3 oz). There is no 140 µm /
4 oz row.** Eurocircuits' highest published outer copper in the classification system is 3 oz, at
0.250 mm. This is exactly the extrapolation the previous wave made — the row *above* the last row,
not a 4 oz row. **0.200 mm is the 2 oz (70 µm) row exactly.**

---

## 8. OSH Park — services list (heaviest copper offered)

URL: https://oshpark.com/

> | **2oz-0.8mm** | Thinner boards with twice the copper | 3 copies for $5/square inch | ... |
> | **4 Layer** | More layers and improved RF | ... |
> | **6 Layer** | Even more layers for improved RF | ... |

**Evidence of absence: the entire service line-up is 1 oz, with a single 2 oz 2-layer service
("2oz-0.8mm"). No 4 oz service exists.**

---

## Checked, could not be used (declared, not silently dropped)

| vendor | why |
|---|---|
| **Würth Elektronik** | `we-online.com` design-rules PDF returns HTTP 403 (Akamai "Access Denied"); the `wedirekt.com` mirror (`basic_design-guide_110325_en_web.pdf`, 1,306,679 B) is only 6 pages and contains no copper-thickness / min-track table (PyMuPDF text search for 140/105/70 µm + "copper" = 0 hits). **UNVERIFIED for Würth.** |
| **Candor Industries** | Design-limits page gives min trace 0.005″ standard / 0.003″ and 0.002″ as cost adders, but **no copper-weight axis**, so it cannot answer the 4 oz question; their heavy-copper product page body did not render through `web_fetch`. **Not used as evidence either way.** |
| **Sierra Circuits** | Public capability pages carry marketing bullets (2 mil trace/space, 1.5 mil) with **no copper-weight-indexed table**; the trace-and-space handbook body is gated behind a download form. No 4 oz row could be retrieved. **UNVERIFIED.** |
| **Ruwel / Schweizer, TTM, Elco** | no public capability table retrievable (search returned nothing, pages login/quote-gated). **UNVERIFIED.** |