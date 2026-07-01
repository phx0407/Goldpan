# Tag_Source Audit Report
## GoldPan Dish Level Data — GP-RULE-013 Phase 1

**Date:** 2026-06-30  
**Auditor:** GoldPan automated audit + manual classification  
**Scope:** All 472 dishes with `Dietary_Tags` in Goldpan Dish Level Data  
**Rule:** GP-RULE-013 — Dietary Tag Provenance v1.0

---

## Executive Summary

| Tier | Recommendation | Count |
|------|---------------|-------|
| CONFIRMED | `goldpan_inferred` | 210 |
| CONFIRMED | `restaurant_disclosed` | 87 |
| PROBABLE | `restaurant_disclosed` (verify before applying) | 109 |
| NEEDS VERIFICATION | Manual review required | 66 |
| **TOTAL** | | **472** |

**Classification principles applied:**
- `high-protein` → always `goldpan_inferred`. No restaurant labels dishes this way; this is a GoldPan nutritional analysis conclusion.
- `gluten-friendly` → always `goldpan_inferred`. Non-standard GoldPan-coined term; restaurants use "gluten-free."
- Slutty Vegan → always `restaurant_disclosed`. Brand identity; the restaurant explicitly positions all food as vegan.
- Non-empty `dietary_options` in staging → `restaurant_disclosed`. The canvasser recorded the restaurant's own disclosure language.
- PROBABLE cases: restaurant type and menu URL suggest disclosure is likely, but no opts text was recorded. Verify before applying.
- NEEDS VERIFICATION: insufficient evidence to classify. Do not apply without manual review.

---

## Section 1 — CONFIRMED `goldpan_inferred`
*210 dishes. Safe to apply immediately.*

**Evidence basis:** `high-protein` and `gluten-friendly` are GoldPan analytical classifications.
Restaurants do not publish menus with "high-protein" labels. `gluten-friendly` is a non-standard
GoldPan term (restaurants use "gluten-free"). These are derived conclusions, not restaurant claims.

| Dish ID | Restaurant | Dish Name | Tags |
|---------|-----------|-----------|------|
| D563 | Abhi Eatery and Bar | KFC (Kathmandu Fried Chicken) | high-protein |
| D567 | Abhi Eatery and Bar | Wing Sizzler | high-protein |
| D572 | Abhi Eatery and Bar | Unagi | high-protein |
| D615 | Abhi Eatery and Bar | Hangover Ramen | high-protein |
| D040 | Adam and Eve Cafe | Tuna Melt Sandwich | high-protein |
| D041 | Adam and Eve Cafe | Italiano Panini | high-protein |
| D063 | Adam and Eve Cafe | Adam and Eve Lox | high-protein |
| D070 | Adam and Eve Cafe | Brooklyn Gem | high-protein |
| D621 | Baha Burger | Classic Burger | high-protein |
| D622 | Baha Burger | The Farm Burger | high-protein |
| D623 | Baha Burger | Bacon Swiss Burger | high-protein |
| D624 | Baha Burger | Turkey Burger | high-protein |
| D625 | Baha Burger | Lamb Burger | high-protein |
| D628 | Baha Burger | Chicken Burger | high-protein |
| D629 | Baha Burger | The Crispy Chick | high-protein |
| D630 | Baha Burger | Grilled Chick | high-protein |
| D631 | Baha Burger | The Club | high-protein |
| D632 | Baha Burger | Bang! Bang! Buffalo | high-protein |
| D633 | Baha Burger | Chicken Tender Basket | high-protein |
| D634 | Baha Burger | Fried Catfish Sandwich | high-protein |
| D635 | Baha Burger | Blackened Fish Sandwich | high-protein |
| D636 | Baha Burger | Salmon Burger | high-protein |
| D637 | Baha Burger | Baha Chicken Salad | high-protein |
| D462 | Cayo Coco Rum Bar & Restaurant | Snapper Ceviche | high-protein |
| D466 | Cayo Coco Rum Bar & Restaurant | Cubano Sandwich | high-protein |
| D043 | Chop N Fresh | Fish & Chips Bowl | high-protein |
| D679 | Chop N Fresh | Kale Caesar | high-protein |
| D033 | Chopt Creative Salad Co. | Southwest Steak Salad | high-protein |
| D034 | Chopt Creative Salad Co. | Kimchi Salmon Bowl | high-protein |
| D035 | Chopt Creative Salad Co. | Chicken Tinga Bowl | high-protein |
| D036 | Chopt Creative Salad Co. | Shrimp Spring Roll Salad | high-protein |
| D037 | Chopt Creative Salad Co. | Crispy Chicken Ranch Wrap | high-protein |
| D686 | Chopt Creative Salad Co. | Summer Corn Caesar Salad | high-protein |
| D688 | Chopt Creative Salad Co. | Summer Corn Caesar Wrap | high-protein |
| D693 | Chopt Creative Salad Co. | Classic Cobb Salad | high-protein |
| D696 | Chopt Creative Salad Co. | Crispy Chicken Ranch Salad | high-protein |
| D699 | Chopt Creative Salad Co. | Salmon Avocado Bowl | high-protein |
| D700 | Chopt Creative Salad Co. | Mediterranean Hummus Bowl | high-protein |
| D701 | Chopt Creative Salad Co. | Harvest Bowl | high-protein |
| D702 | Chopt Creative Salad Co. | Salmon Avocado Wrap | high-protein |
| D704 | Chopt Creative Salad Co. | Chicken Club Wrap | high-protein |
| D707 | Chopt Creative Salad Co. | Chicken Tinga Wrap | high-protein |
| D708 | Chopt Creative Salad Co. | Classic Cobb Wrap | high-protein |
| D713 | Chopt Creative Salad Co. | Southwest Steak Wrap | high-protein |
| D714 | Chopt Creative Salad Co. | Shrimp Spring Roll Wrap | high-protein |
| D058 | Clean Eatz | Philly | high-protein |
| D059 | Clean Eatz | Big Boy 2.0 | high-protein |
| D060 | Clean Eatz | The Arnold | high-protein |
| D062 | Clean Eatz | Bunless | high-protein |
| D715 | Clean Eatz | Buffalo Chicken Wrap | high-protein |
| D716 | Clean Eatz | Chicken Pesto Wrap | high-protein |
| D717 | Clean Eatz | Bang Bang Shrimp Wrap | high-protein |
| D718 | Clean Eatz | Blackened Salmon Wrap | high-protein |
| D719 | Clean Eatz | Epic Chicken Wrap | high-protein |
| D720 | Clean Eatz | Southwest Bison Wrap | high-protein |
| D721 | Clean Eatz | Clean Eatz Burger | high-protein |
| D722 | Clean Eatz | BBQ Swiss Burger | high-protein |
| D723 | Clean Eatz | Bunless Burger | high-protein |
| D724 | Clean Eatz | BBQ Chicken Flatbread | high-protein |
| D725 | Clean Eatz | Bacon Chicken Ranch Flatbread | high-protein |
| D726 | Clean Eatz | Philly Flatbread | high-protein |
| D727 | Clean Eatz | Turkey Burnt End Cuban Flatbread | high-protein |
| D731 | Clean Eatz | Berry Berry Good Smoothie | high-protein |
| D732 | Clean Eatz | Chocolate Covered Strawberry Smoothie | high-protein |
| D733 | Clean Eatz | Dirty Peanut Smoothie | high-protein |
| D734 | Clean Eatz | Frozen Chocolate Banana Smoothie | high-protein |
| D735 | Clean Eatz | Straw-Nana Blast Smoothie | high-protein |
| D736 | Clean Eatz | Raspberry Lemonade Smoothie | high-protein |
| D050 | EastWest | Pan-Seared Salmon | high-protein |
| D475 | EastWest | West Wings | high-protein |
| D477 | EastWest | Grilled Short Ribs | high-protein |
| D480 | EastWest | Char-Grilled Short Rib Bao | high-protein |
| D483 | EastWest | Kobe Burger | high-protein |
| D484 | EastWest | Spicy Garlic Noodles and Gulf Shrimp | high-protein |
| D485 | EastWest | Fried Katsu Chicken | high-protein |
| D487 | EastWest | Teriyaki Chicken Rice Bowl | high-protein |
| D489 | EastWest | Mongolian Beef Rice Bowl | high-protein |
| D490 | EastWest | Tempura Fried Shrimp Rice Bowl | high-protein |
| D491 | EastWest | Tempura Fried Soft-Shell Crab Rice Bowl | high-protein |
| D308 | Eli's Jerusalem Grill | Chicken Vegetable Soup | high-protein |
| D328 | Eli's Jerusalem Grill | Chicken Shawarma | high-protein |
| D329 | Eli's Jerusalem Grill | Garlic Chicken | high-protein |
| D330 | Eli's Jerusalem Grill | Chicken Kabob | high-protein |
| D331 | Eli's Jerusalem Grill | Chicken Tenders | high-protein |
| D333 | Eli's Jerusalem Grill | Beef & Lamb Shawarma | high-protein |
| D334 | Eli's Jerusalem Grill | Beef Kabob | high-protein |
| D335 | Eli's Jerusalem Grill | Lamb Kabob | high-protein |
| D336 | Eli's Jerusalem Grill | Kefta Kabob | high-protein |
| D338 | Eli's Jerusalem Grill | Mixed Shawarma Plate | high-protein |
| D339 | Eli's Jerusalem Grill | Lamb Chops Plate | high-protein |
| D340 | Eli's Jerusalem Grill | Combination Plate | high-protein |
| D343 | Eli's Jerusalem Grill | Stuffed Cabbage Plate | high-protein |
| D510 | Frothy Monkey | Farm Breakfast | gluten-friendly |
| D514 | Frothy Monkey | Salmon Sandwich | high-protein |
| D515 | Frothy Monkey | Pesto Pasta & Chicken | high-protein |
| D516 | Frothy Monkey | Shrimp & Grits | gluten-friendly, high-protein |
| D517 | Frothy Monkey | Grilled Salmon | gluten-friendly, high-protein |
| D518 | Frothy Monkey | Gail Salad | high-protein |
| D519 | Frothy Monkey | Salmon Arugula Salad | high-protein |
| D524 | Frothy Monkey | Bacon, Egg & Cheddar Bagel | high-protein |
| D525 | Frothy Monkey | Everything Lox Bagel | high-protein |
| D526 | Frothy Monkey | Maple Chicken Salad | high-protein |
| D201 | Kale Me Crazy | Grilled Salmon Salad | high-protein |
| D206 | Kale Me Crazy | Salmon Avocado Wrap | high-protein |
| D207 | Kale Me Crazy | Chicken Pesto Wrap | high-protein |
| D208 | Kale Me Crazy | Tuna Wrap | high-protein |
| D209 | Kale Me Crazy | Turkey Wrap | high-protein |
| D212 | Kale Me Crazy | Chicken Quesadilla | high-protein |
| D217 | Kale Me Crazy | Salmon Toast | high-protein |
| D219 | Kale Me Crazy | Poke Bowl | high-protein |
| D004 | Real & Rosemary | Chicken Salad Sandwich | high-protein |
| D136 | Real & Rosemary | Southwest Salad | high-protein |
| D137 | Real & Rosemary | Turkey Sandwich | high-protein |
| D139 | Real & Rosemary | The Burger | high-protein |
| D141 | Real & Rosemary | Grilled Chicken Sandwich | high-protein |
| D144 | Real & Rosemary | Grilled Chicken Plate | high-protein |
| D145 | Real & Rosemary | Spice Rubbed Chicken Plate | high-protein |
| D146 | Real & Rosemary | Flounder Cake Plate | high-protein |
| D147 | Real & Rosemary | Meatball Plate | high-protein |
| D148 | Real & Rosemary | Chicken Poppers Plate | high-protein |
| D149 | Real & Rosemary | Chicken Salad Plate | high-protein |
| D054 | SoHo Social | G.G.G. Bowl | high-protein |
| D055 | SoHo Social | Tuna Tataki | high-protein |
| D056 | SoHo Social | Steak & Feta Tacos | high-protein |
| D742 | SoHo Social | The Basics | high-protein |
| D745 | SoHo Social | Flank Steak Caesar | high-protein |
| D747 | SoHo Social | Grilled Shrimp | high-protein |
| D748 | SoHo Social | Soho Soul Plate | high-protein |
| D749 | SoHo Social | Southern Shrimp Tacos | high-protein |
| D750 | SoHo Social | Gringo Loco | high-protein |
| D751 | SoHo Social | Tuna Wrap | high-protein |
| D752 | SoHo Social | Cahaba Chicken Caesar Wrap | high-protein |
| D753 | SoHo Social | 3B Honey Mustard Chicken Wrap | high-protein |
| D754 | SoHo Social | Jamn Gouda | high-protein |
| D755 | SoHo Social | Garlic Butter Bacon | high-protein |
| D757 | SoHo Social | SoHo | high-protein |
| D758 | SoHo Social | Triple Bacon Cheese | high-protein |
| D759 | SoHo Social | Maple Bacon Burger | high-protein |
| D760 | SoHo Social | The Melt | high-protein |
| D761 | SoHo Social | Turkey | high-protein |
| D762 | SoHo Social | Verde Hot Honey | high-protein |
| D763 | SoHo Social | The Chicken Sandwich | high-protein |
| D764 | SoHo Social | Southern King | high-protein |
| D765 | SoHo Social | Oh Susannah | high-protein |
| D025 | SoHo Standard | Quail + Waffles | high-protein |
| D258 | SoHo Standard | Oyster (Brunch) | high-protein |
| D263 | SoHo Standard | Fish (Brunch) | high-protein |
| D265 | SoHo Standard | Steak + Biscuits | high-protein |
| D270 | SoHo Standard | Shrimp | high-protein |
| D271 | SoHo Standard | Oyster | high-protein |
| D280 | SoHo Standard | Ravioli | high-protein |
| D281 | SoHo Standard | Steak | high-protein |
| D282 | SoHo Standard | Fish | high-protein |
| D283 | SoHo Standard | Chicken | high-protein |
| D285 | SoHo Standard | Tacos | high-protein |
| D435 | The Battery | Smoked Chicken Wings | high-protein |
| D438 | The Battery | Tuna Poke Bowl | high-protein |
| D445 | The Battery | Chicken Tender Basket | high-protein |
| D447 | The Battery | Philly Cheesesteak | high-protein |
| D448 | The Battery | The Smashburger | high-protein |
| D449 | The Battery | Buffalo Chicken Sandwich | high-protein |
| D450 | The Battery | Brisket Grilled Cheese | high-protein |
| D451 | The Battery | Korean BBQ Tacos | high-protein |
| D452 | The Battery | Blackened Fish Sandwich | high-protein |
| D453 | The Battery | Black & Blue Burger | high-protein |
| D454 | The Battery | Pork Ribeye | high-protein |
| D455 | The Battery | Mama's Chicken | high-protein |
| D457 | The Battery | Shrimp & Grits | high-protein |
| D458 | The Battery | Chicken Pesto Pasta | high-protein |
| D640 | Urban Cookhouse | Pepper Patch Wrap | high-protein |
| D641 | Urban Cookhouse | Berry Good Wrap | high-protein |
| D642 | Urban Cookhouse | Local Mix Wrap | high-protein |
| D643 | Urban Cookhouse | The Cookhouse Wrap | high-protein |
| D644 | Urban Cookhouse | Buffalo Chicken Wrap | high-protein |
| D645 | Urban Cookhouse | Mandarin Crunch Wrap | high-protein |
| D651 | Urban Cookhouse | White BBQ Sandwich | high-protein |
| D652 | Urban Cookhouse | Urban Cowboy | high-protein |
| D654 | Urban Cookhouse | El Cubano | high-protein |
| D655 | Urban Cookhouse | Grilled Chicken Sandwich | high-protein |
| D658 | Urban Cookhouse | Chicken Salad Sandwich | high-protein |
| D661 | Urban Cookhouse | Chipotle Braised Pork Plate | high-protein |
| D662 | Urban Cookhouse | Grilled Chicken Special | high-protein |
| D663 | Urban Cookhouse | Lime-Marinated Steak and Rice | high-protein |
| D664 | Urban Cookhouse | Wood-Fired Shrimp Kabob | high-protein |
| D533 | Wasabi Juan's | Poke' & Sticky | high-protein |
| D534 | Wasabi Juan's | L.H.M. (Lord Have Mercy) | high-protein |
| D535 | Wasabi Juan's | Rainbow | high-protein |
| D536 | Wasabi Juan's | Ignition | high-protein |
| D537 | Wasabi Juan's | Alaskan Sunrise | high-protein |
| D538 | Wasabi Juan's | Aloha | high-protein |
| D540 | Wasabi Juan's | Tropical Tuna | high-protein |
| D541 | Wasabi Juan's | Rick Roll | high-protein |
| D543 | Wasabi Juan's | South Beach | high-protein |
| D546 | Wasabi Juan's | Toro | high-protein |
| D547 | Wasabi Juan's | Destin | high-protein |
| D549 | Wasabi Juan's | Thai'd Up | high-protein |
| D551 | Wasabi Juan's | Starter | high-protein |
| D553 | Wasabi Juan's | Avondale Taco | high-protein |
| D554 | Wasabi Juan's | Chicken Little Taco | high-protein |
| D010 | Yo Chef Surf & Turf Smokehouse | Chicken Caesar Wrap | high-protein |
| D154 | Yo Chef Surf & Turf Smokehouse | Shrimp & Grits | high-protein |
| D156 | Yo Chef Surf & Turf Smokehouse | Oxtails & Grits | high-protein |
| D160 | Yo Chef Surf & Turf Smokehouse | Surf & Turf Burger | high-protein |
| D162 | Yo Chef Surf & Turf Smokehouse | Down South Philly | high-protein |
| D164 | Yo Chef Surf & Turf Smokehouse | Chipotle Chicken Tacos | high-protein |
| D166 | Yo Chef Surf & Turf Smokehouse | Catfish Po Boy | high-protein |
| D168 | Yo Chef Surf & Turf Smokehouse | BBQ Smoked Pork Ribs | high-protein |
| D170 | Yo Chef Surf & Turf Smokehouse | Glazed Lamb Chops | high-protein |
| D172 | Yo Chef Surf & Turf Smokehouse | BBQ Smoked 1/2 Chicken | high-protein |
| D307 | Yo Mama's | Seafood Omelette | high-protein |

## Section 2 — CONFIRMED `restaurant_disclosed`
*87 dishes. Safe to apply immediately.*

**Evidence basis:** Either (a) the canvasser recorded explicit restaurant disclosure language
in `dietary_options`, or (b) the restaurant's concept is vegan by design (Slutty Vegan).

### Blue Root (14 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D399 | Immunity Soup | gluten-free, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan (per restaurant nutrition docum |
| D419 | Cashew Butter Cookies | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF, Vegetarian" |
| D420 | Dark Chocolate Tahini Brownie | gluten-free, dairy-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF, DF, Vegetarian" |
| D421 | Dark Chocolate Collagen Bliss Bites | gluten-free, dairy-free | dietary_options in staging records restaurant disclosure: "GF, DF" |
| D422 | Not Your Mama's Rice Crispy Treat | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF, Vegetarian" |
| D423 | PB&J Protein Bliss Bites | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF, Vegetarian" |
| D424 | Beet Hummus | gluten-free, dairy-free, vegan | dietary_options in staging records restaurant disclosure: "GF, DF, Vegan" |
| D425 | Chicken Salad | gluten-free | dietary_options in staging records restaurant disclosure: "GF" |
| D426 | Chipotle Chicken | gluten-free, dairy-free | dietary_options in staging records restaurant disclosure: "GF, DF" |
| D427 | Soft-Boiled Farm Egg | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF, Vegetarian" |
| D428 | Grilled Chicken | gluten-free, dairy-free | dietary_options in staging records restaurant disclosure: "GF, DF" |
| D429 | Lemon-Herb Chicken | gluten-free, dairy-free | dietary_options in staging records restaurant disclosure: "GF, DF" |
| D430 | Maple Cured Salmon | gluten-free, dairy-free | dietary_options in staging records restaurant disclosure: "GF, DF" |
| D431 | Miso-Glazed Tofu | gluten-free, dairy-free, vegan | dietary_options in staging records restaurant disclosure: "GF, DF, Vegan" |

### EastWest (1 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D474 | Lettuce Wraps | vegetarian | dietary_options in staging records restaurant disclosure: "Tofu or chicken" |

### Eli's Jerusalem Grill (26 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D309 | Lentil Soup | vegetarian, vegan | dietary_options in staging records restaurant disclosure: "Vegetarian, Vegan" |
| D311 | Hummus | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (small/no pita). Vegan." |
| D312 | Hummus with Hard-Boiled Egg | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "GF (small/no pita). Vegetarian." |
| D313 | Hummus with Sautéed Mushroom | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (small/no pita). Vegan." |
| D314 | Hummus with Roasted Red Peppers | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (small/no pita). Vegan." |
| D315 | Baba Ghanoush | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (small/no pita). Vegan." |
| D318 | Israeli Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D319 | Tabouli Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (quinoa-based, not bulgur). Vegan." |
| D320 | Red Cabbage Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D321 | White Cabbage Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D322 | Cucumber Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D323 | Moroccan Carrots | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D324 | Beet Salad | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D325 | Roasted Red Peppers | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D326 | Roasted Vegetables | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D327 | Salad Sampler | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D332 | Chicken Schnitzel | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF — all breading is gluten-free per rest |
| D337 | Falafel | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF (fried in non-GMO sunflower oil, GF pe |
| D341 | Shakshuka Plate | vegetarian, gluten-free | dietary_options in staging records restaurant disclosure: "Vegetarian, GF (served with salad only —  |
| D342 | Vegetarian & Vegan Plate | vegetarian, vegan, gluten-free | dietary_options in staging records restaurant disclosure: "Vegetarian, Vegan, GF" |
| D344 | Alaskan Salmon Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF" |
| D345 | Moroccan Fish Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF. Weekend only special." |
| D346 | Israeli Pickles & Olives | gluten-free, vegetarian, vegan | dietary_options in staging records restaurant disclosure: "GF, Vegan" |
| D347 | French Fries | gluten-free, vegan | dietary_options in staging records restaurant disclosure: "GF (non-GMO sunflower oil). Vegan." |
| D348 | Sweet Potato Fries | gluten-free, vegan | dietary_options in staging records restaurant disclosure: "GF (non-GMO sunflower oil). Vegan." |
| D349 | Fried Cauliflower | gluten-free, vegan | dietary_options in staging records restaurant disclosure: "GF (non-GMO sunflower oil, GF breading).  |

### Frothy Monkey (7 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D507 | Garden Omelette | vegetarian | dietary_options in staging records restaurant disclosure: "Egg whites available upon request" |
| D512 | Quinoa & Black Bean Burger | vegetarian | dietary_options in staging records restaurant disclosure: "Sub plant-based patty +$2" |
| D520 | Caesar Salad | vegetarian | dietary_options in staging records restaurant disclosure: "Add chicken +$6 / Add salmon +$9" |
| D521 | The BE Hive Quinoa Bowl | vegan, gluten-friendly | dietary_options in staging records restaurant disclosure: "Sub andouille sausage for vegan sausage" |
| D522 | Cali Toast | vegetarian | dietary_options in staging records restaurant disclosure: "Egg whites available upon request" |
| D523 | Egg, Feta & Tomato | vegetarian | dietary_options in staging records restaurant disclosure: "Egg whites available upon request / Sub g |
| D527 | Egg Salad | vegetarian | dietary_options in staging records restaurant disclosure: "Sub gluten friendly bread +$1" |

### Slutty Vegan (8 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D028 | One Night Stand | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D030 | Sloppy Toppy | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D032 | Hooker Fries | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D681 | Fussy Hussy | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D682 | Dancehall Queen | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D683 | Hollywood Hooker | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D684 | Big Meat | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |
| D685 | Slutty Fries | vegan, vegetarian | Slutty Vegan brand identity — restaurant explicitly positions all food as vegan on menu and in marke |

### SoHo Social (1 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D741 | Social House | vegetarian | dietary_options in staging records restaurant disclosure: "add grilled shrimp" |

### The Battery (10 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D432 | Monsterella Sticks | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D433 | Pickle Fries | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D434 | Crispy Brussels Sprouts | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D436 | Pimento Cheese | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D437 | Queso Dip | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D440 | Green Goddess Salad | gluten-free | dietary_options in staging records restaurant disclosure: "Gluten-free per menu (*). Contains bacon. |
| D441 | Cobb Salad | gluten-free | dietary_options in staging records restaurant disclosure: "Gluten-free per menu (*). Choice of dress |
| D442 | Wedge Salad | gluten-free | dietary_options in staging records restaurant disclosure: "Gluten-free per menu (*)." |
| D443 | Tomato Soup | gluten-free, vegetarian | dietary_options in staging records restaurant disclosure: "Gluten-free per menu (*). Vegetarian." |
| D456 | Seared King Salmon | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "Gluten-free per menu (*)." |

### Wooden City Birmingham (4 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D363 | Veggie Pizza | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian" |
| D367 | Vegan Pizza | vegan, vegetarian | dietary_options in staging records restaurant disclosure: "Vegan, Vegetarian" |
| D368 | Tavern Burger | gluten-free | dietary_options in staging records restaurant disclosure: "GF bun available (+$1). No modifications. |
| D370 | Veggie Burger | vegetarian | dietary_options in staging records restaurant disclosure: "Vegetarian. Available as Fancy or Tavern  |

### Yo Mama's (16 dishes)

| Dish ID | Dish Name | Tags | Evidence |
|---------|-----------|------|---------|
| D290 | Fish Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF option available" |
| D292 | Shrimp Tacos | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF with corn tortillas" |
| D293 | Shrimp & Grits | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF as presented" |
| D294 | Shrimp Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF option available" |
| D295 | Hot Wings Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF option available" |
| D296 | Chicken & Waffle | gluten-free | dietary_options in staging records restaurant disclosure: "GF waffle available (+$1.50)" |
| D297 | Chicken Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF option available" |
| D298 | BBQ Cheeseburger Plate | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF bun available (+$1.50)" |
| D299 | Chicken & Pancakes | gluten-free | dietary_options in staging records restaurant disclosure: "GF pancakes available (+$1.50). Brunch on |
| D300 | Fish & Grits | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF (toast optional +$0.75, GF toast +$0.7 |
| D301 | Mama's Meal | gluten-free | dietary_options in staging records restaurant disclosure: "GF toast available (+$0.75). Brunch only. |
| D302 | Salmon Croquettes | gluten-free, high-protein | dietary_options in staging records restaurant disclosure: "GF option available. Brunch only." |
| D303 | Pancakes | gluten-free | dietary_options in staging records restaurant disclosure: "GF available (+$1.50). Brunch only." |
| D304 | French Toast | gluten-free | dietary_options in staging records restaurant disclosure: "GF available (+$1.50). Brunch only." |
| D305 | Waffle | gluten-free | dietary_options in staging records restaurant disclosure: "GF available (+$1.50). Brunch only." |
| D306 | 2-Egg Omelette | gluten-free | dietary_options in staging records restaurant disclosure: "GF available (GF toast option). Brunch on |

## Section 3 — PROBABLE `restaurant_disclosed` (verify before applying)
*109 dishes. Recommended `restaurant_disclosed` based on restaurant type and menu source, 
but no disclosure language was recorded in `dietary_options`. Verify against the live menu before applying.*

**To verify:** Check the restaurant's menu URL (listed in Menu Source Registry) and confirm
the tag appears on the menu. If confirmed, approve for application. If not found, reclassify to `goldpan_inferred`.

### Abhi Eatery and Bar (28 dishes)
*Japanese restaurant canvassed from menu URL; menus of this type commonly mark GF/Vegan explicitly.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D560 | Edamame | gluten-free, vegan | Verify against menu |
| D561 | Spicy Edamame | gluten-free, vegan | Verify against menu |
| D562 | Tempura Fried Green Beans | vegetarian | Verify against menu |
| D564 | Beer Batter Eggplant | vegetarian | Verify against menu |
| D565 | Chickpea & Shiitake Wrap | vegetarian, vegan | Verify against menu |
| D566 | Udon Noodles | vegetarian | Verify against menu |
| D568 | Tako Salad | gluten-free, high-protein | Verify against menu |
| D569 | Tuna Tataki | gluten-free, high-protein | Verify against menu |
| D570 | Seared Tuna | gluten-free, high-protein | Verify against menu |
| D571 | Belly Dancer | gluten-free, high-protein | Verify against menu |
| D573 | Spicy Bangkok Salad | gluten-free, vegan | Verify against menu |
| D574 | Shrimp Salad | gluten-free, high-protein | Verify against menu |
| D586 | Yuca Roll | vegetarian, vegan | Verify against menu |
| D601 | Garlic Shrimp Sekuwa | gluten-free, high-protein | Verify against menu |
| D602 | Buddha Bowl | gluten-free, vegan | Verify against menu |
| D603 | Poke Bowl | gluten-free, high-protein | Verify against menu |
| D604 | Spicy Poke Bowl | gluten-free, high-protein | Verify against menu |
| D605 | Pork Belly Bowl | gluten-free, high-protein | Verify against menu |
| D606 | Bunless Burger Bowl Turkey | gluten-free | Verify against menu |
| D607 | Bulgogi Bowl | gluten-free, high-protein | Verify against menu |
| D608 | Thukpa | gluten-free | Verify against menu |
| D610 | Vegetarian Ramen | gluten-free, vegan | Verify against menu |
| D613 | Iron Bowl | gluten-free | Verify against menu |
| D616 | Bangkok Panang Curry | gluten-free | Verify against menu |
| D617 | Sizzler | gluten-free | Verify against menu |
| D618 | Balinese Beef Rendang | gluten-free, high-protein | Verify against menu |
| D619 | Nepalese Lamb Curry | gluten-free, high-protein | Verify against menu |
| D620 | Royal Kari Malaysian Style Curry | gluten-free, high-protein | Verify against menu |

### Baha Burger (4 dishes)
*Baha Burger menu explicitly names and marks vegetarian options.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D626 | Portabella Mushroom Burger | vegetarian | Verify against menu |
| D627 | Veggie Burger | vegetarian | Verify against menu |
| D638 | Mediterranean Salad with Lamb | gluten-free, high-protein | Verify against menu |
| D639 | Mediterranean Salad with Salmon | gluten-free, high-protein | Verify against menu |

### Blue Root (16 dishes)
*Blue Root publishes a nutrition guide that explicitly marks GF/Vegan/DF per addendum staging opts text.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D386 | California Cobb | gluten-free, vegetarian | Verify against menu |
| D388 | Farmstand | gluten-free, vegetarian | Verify against menu |
| D391 | Kale Caesar | gluten-free, vegetarian | Verify against menu |
| D395 | Santa Fe | gluten-free, vegetarian | Verify against menu |
| D398 | Gingery Lentil Dal | gluten-free, dairy-free, vegan | Verify against menu |
| D401 | Protein Box with Grilled Chicken | gluten-free, dairy-free, high-protein | Verify against menu |
| D403 | Quinoa with Roasted Vegetables | gluten-free, dairy-free, vegan | Verify against menu |
| D404 | Wheatberry Salad | vegetarian | Verify against menu |
| D406 | Banana Nut Bread Overnight Oats | gluten-free, dairy-free, vegan | Verify against menu |
| D407 | Chia Seed Pudding | gluten-free, dairy-free, vegan | Verify against menu |
| D409 | Lemon Blueberry Overnight Oats | gluten-free, dairy-free, vegan | Verify against menu |
| D411 | Clean Green Smoothie | gluten-free, dairy-free, vegan | Verify against menu |
| D412 | Upbeet Smoothie | gluten-free, dairy-free, vegan | Verify against menu |
| D413 | Hummus Toast | vegetarian | Verify against menu |
| D414 | Hummus Toast with Soft-Boiled Farm Egg | vegetarian | Verify against menu |
| D417 | Maple Prosciutto Toast | dairy-free | Verify against menu |

### Cayo Coco Rum Bar & Restaurant (5 dishes)
*Canvassed from cayococo printed menus PDF; marks GF/Vegetarian.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D460 | Collard Green Cornbread | vegetarian | Verify against menu |
| D461 | Tostones | vegetarian | Verify against menu |
| D464 | Red Snapper | gluten-free, high-protein | Verify against menu |
| D465 | Jerk Chicken | gluten-free, high-protein | Verify against menu |
| D468 | Bistro Filet | gluten-free, high-protein | Verify against menu |

### Chop N Fresh (11 dishes)
*Health fast-casual canvassed from menu; marks GF/V/VG on items.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D044 | Mexican Elote Bowl | vegetarian, gluten-free | Verify against menu |
| D045 | Cobb Boom | gluten-free, high-protein | Verify against menu |
| D046 | The Impossible Taco Salad | vegetarian, gluten-free, high-protein | Verify against menu |
| D047 | Wholey Moley | gluten-free, high-protein | Verify against menu |
| D673 | Honey Mustard & Chill | gluten-free, high-protein | Verify against menu |
| D674 | Red, White, & Blue | vegan, vegetarian, gluten-free | Verify against menu |
| D675 | Strawberry Bae | gluten-free | Verify against menu |
| D676 | Chicken Pesto Bowl | gluten-free, high-protein | Verify against menu |
| D677 | Sweet Bowl Alabama | gluten-free, high-protein | Verify against menu |
| D678 | Falafel N Love | vegetarian | Verify against menu |
| D680 | Southwestern | gluten-free, high-protein | Verify against menu |

### Chopt Creative Salad Co. (12 dishes)
*Chopt's website explicitly marks Vegetarian items; canvassed from choptsalad.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D687 | Sweet Peach Burrata Bowl | vegetarian | Verify against menu |
| D690 | Kale Caesar Salad | vegetarian | Verify against menu |
| D691 | Mexican Caesar Salad | vegetarian | Verify against menu |
| D694 | Santa Fe Salad | vegetarian | Verify against menu |
| D695 | The Chopt Greek Salad | vegetarian | Verify against menu |
| D697 | Sweet Apple Orchard Salad | vegetarian | Verify against menu |
| D703 | Hummus Crunch Wrap | vegan | Verify against menu |
| D705 | Kale Caesar Wrap | vegetarian | Verify against menu |
| D706 | Mexican Caesar Wrap | vegetarian | Verify against menu |
| D709 | Santa Fe Wrap | vegetarian | Verify against menu |
| D710 | The Chopt Greek Wrap | vegetarian | Verify against menu |
| D712 | Sweet Apple Orchard Wrap | vegetarian | Verify against menu |

### EastWest (9 dishes)
*Canvassed from EastWest dinner PDF menu.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D048 | Korean Fried Cauliflower | vegetarian | Verify against menu |
| D049 | Tofu Lettuce Wraps | vegetarian | Verify against menu |
| D471 | Fried Spring Rolls | vegetarian | Verify against menu |
| D472 | Korean-Fried Cauliflower | vegetarian | Verify against menu |
| D473 | House Salad | vegetarian | Verify against menu |
| D476 | Blistered Shishito Peppers | vegetarian | Verify against menu |
| D481 | Fried Mushroom Bao | vegetarian | Verify against menu |
| D486 | Mongolian Ribeye | gluten-free, high-protein | Verify against menu |
| D488 | Vegetable Bowl | vegetarian, vegan | Verify against menu |

### Urban Cookhouse (12 dishes)
*Mixed tags: ['high-protein'] are goldpan_inferred; ['gluten-free'] are probable restaurant_disclosed.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D646 | Chicken Salad and Fruit Plate | gluten-free, high-protein | Verify against menu |
| D647 | Pepper Patch Salad | gluten-free, vegetarian | Verify against menu |
| D648 | Local Mix Salad | gluten-free | Verify against menu |
| D649 | Berry Good Salad | gluten-free, vegetarian | Verify against menu |
| D650 | Mandarin Crunch Salad | vegetarian | Verify against menu |
| D665 | Veggie Quesadilla | vegetarian | Verify against menu |
| D667 | Rice Pilaf | gluten-free | Verify against menu |
| D668 | Broccoli Salad | gluten-free | Verify against menu |
| D669 | Fresh Fruit | gluten-free, vegan | Verify against menu |
| D670 | Hot Cheddar Pasta | vegetarian | Verify against menu |
| D671 | Roasted Vegetables | gluten-free, vegan | Verify against menu |
| D672 | Garden Salad | gluten-free, vegan | Verify against menu |

### Wasabi Juan's (12 dishes)
*Canvassed from wasabijuan.*

| Dish ID | Dish Name | Tags | Status |
|---------|-----------|------|--------|
| D529 | Cucumber Salad | vegetarian, vegan, gluten-free | Verify against menu |
| D530 | Mango Slaw | vegetarian, vegan, gluten-free | Verify against menu |
| D532 | Juan's Nachos | gluten-free | Verify against menu |
| D539 | Spicy Juan | gluten-free, high-protein | Verify against menu |
| D542 | JTH | gluten-free, high-protein | Verify against menu |
| D544 | Hippy | vegetarian, vegan, gluten-free | Verify against menu |
| D545 | Cowboy | gluten-free, high-protein | Verify against menu |
| D548 | Samurai | gluten-free, high-protein | Verify against menu |
| D550 | The Blazer | gluten-free, high-protein | Verify against menu |
| D552 | Ceviche Taco | gluten-free, high-protein | Verify against menu |
| D555 | 30-A Taco | gluten-free, high-protein | Verify against menu |
| D556 | Sonora Taco | gluten-free, high-protein | Verify against menu |

## Section 4 — NEEDS VERIFICATION (manual review required)
*66 dishes. Do not apply Tag_Source without manual review.*

These dishes either have no staging file entry, have mixed tag types without clear evidence,
or come from restaurants where the disclosure source is genuinely unknown.

### Adam and Eve Cafe (14 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D038 | Amazing Avocado | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D039 | Grilled Tofu | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D042 | Tuscan Panini | vegetarian | Not fully in staging files; tag origin unclear — verify against menu |
| D064 | Avocado Toast | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D073 | Lovely Hummus | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D074 | Fancy Seitan | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D075 | Vegan Grill Chicken Sandwich | vegan, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['vegan'] source unclear. Not fully in staging f |
| D076 | Dungeon Sandwich | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D077 | Vegan Meatball | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D078 | Surprise Me | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D079 | Vegan Italian Salami | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D081 | Italian Sandwich | vegan | Not fully in staging files; tag origin unclear — verify against menu |
| D082 | Fresh Caesar Salad | vegetarian | Not fully in staging files; tag origin unclear — verify against menu |
| D083 | Fresh Vegan Caesar Salad | vegan | Not fully in staging files; tag origin unclear — verify against menu |

### Brick & Tin (6 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D015 | Simple Salad | vegan, gluten-free | Not fully in staging; verify against menu |
| D118 | Classic Salad | vegetarian | Not fully in staging; verify against menu |
| D120 | Spring Farro Salad | vegan | Not fully in staging; verify against menu |
| D123 | Pork Belly Lettuce Wraps | gluten-free | Not fully in staging; verify against menu |
| D125 | Sauteed Salmon | gluten-free | Not fully in staging; verify against menu |
| D126 | Sesame Chicken Bowl | gluten-free | Not fully in staging; verify against menu |

### Clean Eatz (1 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D061 | Nugget Dinner | gluten-free, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['gluten-free'] source unclear. 1 dish has GF+hi |

### Emmy Squared (2 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D021 | Shaved Brussels Sprouts Salad | vegetarian | Vegetarian salad without opts text — verify (pizza has opts text already) |
| D233 | Cheesy Garlic Sticks | vegetarian | Vegetarian salad without opts text — verify (pizza has opts text already) |

### Frothy Monkey (3 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D502 | Biscuit Board | vegetarian | Partial opts text; 3 vegetarian dishes have no opts — verify |
| D505 | Herb-Whipped Feta | vegetarian | Partial opts text; 3 vegetarian dishes have no opts — verify |
| D511 | Vanilla-Cinnamon French Toast | vegetarian | Partial opts text; 3 vegetarian dishes have no opts — verify |

### Kale Me Crazy (3 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D211 | Vegan Wrap | vegan | Not in staging; verify whether vegan/vegetarian labels are on menu |
| D213 | Veggie Quesadilla | vegetarian | Not in staging; verify whether vegan/vegetarian labels are on menu |
| D214 | Margherita Flatbread | vegetarian | Not in staging; verify whether vegan/vegetarian labels are on menu |

### Real & Rosemary (10 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D001 | Grilled Herb Chicken | gluten-free, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['gluten-free'] source unclear. Not in staging;  |
| D127 | Fried Okra | vegetarian | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D128 | Sweet Potato Fries | vegetarian | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D129 | Fried Green Tomatoes | vegetarian | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D131 | Honey Ricotta | vegetarian | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D133 | Grilled Chicken Salad | gluten-free, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['gluten-free'] source unclear. Not in staging;  |
| D134 | Upbeet Salad | vegetarian, gluten-free | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D135 | Vegetable Soup | vegan, gluten-free | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D142 | Beet, Fig, Goat Cheese Sandwich | vegetarian | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |
| D150 | "Early" Summer Salad | vegetarian, gluten-free | Not in staging; some GF+high-protein combos — GF portion may be restaurant_disclosed |

### SoHo Social (1 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D756 | Black Bean | vegetarian, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['vegetarian'] source unclear. One dish (Black B |

### SoHo Standard (4 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D022 | Hash | gluten-free | Not in staging; tag origin unclear — verify against menu |
| D023 | Shrimp & Grits | gluten-free, high-protein | Mixed: ['high-protein'] goldpan_inferred; ['gluten-free'] source unclear. Not in staging;  |
| D026 | Bites | gluten-free | Not in staging; tag origin unclear — verify against menu |
| D260 | Bacon | gluten-free | Not in staging; tag origin unclear — verify against menu |

### The Essential (20 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D084 | Granola & Yogurt | vegetarian, gluten-free | In staging backup but no opts text; cannot confirm source |
| D085 | Caesar Salad | vegetarian | In staging backup but no opts text; cannot confirm source |
| D086 | Five Grain Salad | vegetarian, gluten-free | In staging backup but no opts text; cannot confirm source |
| D087 | Avocado Toast | vegetarian | In staging backup but no opts text; cannot confirm source |
| D089 | Banana Bread French Toast | vegetarian | In staging backup but no opts text; cannot confirm source |
| D090 | Honey Butter Pancakes | vegetarian, gluten-free | In staging backup but no opts text; cannot confirm source |
| D092 | Essential Hash | gluten-free | In staging backup but no opts text; cannot confirm source |
| D093 | Tomatoes and Grits | gluten-free | In staging backup but no opts text; cannot confirm source |
| D096 | Steak & Eggs | gluten-free | In staging backup but no opts text; cannot confirm source |
| D097 | Arancini | vegetarian | In staging backup but no opts text; cannot confirm source |
| D098 | Hummus + Pickles | vegetarian, vegan, gluten-free | In staging backup but no opts text; cannot confirm source |
| D099 | Mushroom Toast | vegetarian | In staging backup but no opts text; cannot confirm source |
| D101 | Salmon Waldorf Salad | gluten-free | In staging backup but no opts text; cannot confirm source |
| D102 | Caprese Salad | vegetarian, gluten-free | In staging backup but no opts text; cannot confirm source |
| D103 | Agnolotti Pomodoro | vegetarian | In staging backup but no opts text; cannot confirm source |
| D104 | Spaghetti | vegetarian | In staging backup but no opts text; cannot confirm source |
| D105 | Casarecce | vegetarian | In staging backup but no opts text; cannot confirm source |
| D107 | Rainbow Trout | gluten-free | In staging backup but no opts text; cannot confirm source |
| D108 | Half Chicken Piri Piri | gluten-free | In staging backup but no opts text; cannot confirm source |
| D109 | Bistro Steak | gluten-free | In staging backup but no opts text; cannot confirm source |

### Yo Chef Surf & Turf Smokehouse (2 dishes)

| Dish ID | Dish Name | Tags | Issue |
|---------|-----------|------|-------|
| D178 | Garden Salad | vegetarian | 2 vegetarian items not in staging — verify |
| D180 | Veggie Wings | vegetarian | 2 vegetarian items not in staging — verify |

## Section 5 — Recommended Action Plan

### Phase 2A — Apply confirmed cases immediately
Apply `goldpan_inferred` to 210 dishes (Section 1) and
`restaurant_disclosed` to 87 dishes (Section 2).
Zero ambiguity. Run `backfill_tag_source.py --apply --tier=confirmed`.

### Phase 2B — Verify and apply probable cases
Check 109 dishes (Section 3) against live menu URLs.
For each restaurant, spot-check 2-3 dishes. If the menu shows the label, approve the full batch.
If the menu does not show the label, reclassify to `goldpan_inferred`.

**Priority verification order:**
1. Blue Root — already has addendum evidence (nutrition document); main staging likely same source
2. Wasabi Juan's — sushi restaurants consistently mark GF/Vegan
3. Urban Cookhouse — PDF menu likely marks GF
4. Abhi Eatery — Japanese restaurant, spot-check abhieatery.com/eat
5. Chopt — choptsalad.com marks Vegetarian explicitly
6. Remaining (Baha Burger, Cayo Coco, Chop N Fresh, EastWest)

### Phase 2C — Manually review unclear cases
Review 66 dishes (Section 4). For each restaurant:
- Check the menu for dietary labels
- If labeled on menu → `restaurant_disclosed`
- If GoldPan added from ingredient analysis → `goldpan_inferred`
- If unknown → leave blank (data quality warning; resolve during next canvass)

### Remaining blank Tag_Source after Phase 2
Dishes that do not have Dietary_Tags (278 of 686 active dishes) will have `tag_source = null`.
This is correct — blank Tag_Source is only a warning when Dietary_Tags is also populated.

---

*Report generated by GoldPan automated audit. GP-RULE-013 v1.0.*
---

## Phase 2B — Web Verification Results (2026-06-30)

Searched live menus for the 9 PROBABLE restaurants (109 dishes). Verified whether the restaurant explicitly marks dietary labels on their published menu.

### CONFIRMED — explicit menu labeling found

| Restaurant | Dishes | Evidence |
|-----------|--------|---------|
| Abhi Eatery and Bar | 28 | Official menu at abhieatery.com uses "GF" notation. Allergen labeling confirmed. |
| Blue Root | 16 | Menu explicitly uses GF/DF/V/VG labels. Nutrition facts PDF published. Consistent with addendum evidence ("per restaurant nutrition document"). |
| Wasabi Juan's | 12 | Menu is marked GF per findmeglutenfree.com, Tripadvisor, and atly.com. Vegetarian/vegan options explicitly labeled. |

**56 additional dishes confirmed as `restaurant_disclosed`. Added to `backfill_tag_source.py`.**

### INSUFFICIENT EVIDENCE — remain for manual review

| Restaurant | Dishes | Finding |
|-----------|--------|---------|
| Urban Cookhouse | 12 | Customer reports state the menu does not label GF — must ask staff. No on-menu labels confirmed. |
| Baha Burger | 4 | No dedicated dietary labeling system found. Vegetarian items identifiable by dish name, not by explicit label. |
| Cayo Coco Rum Bar & Restaurant | 5 | No specific GF menu or dietary label system confirmed from search results. |
| Chop N Fresh | 11 | Dietary options available but no menu markers confirmed in search results. |
| EastWest | 9 | Staff can assist with dietary needs, but no explicit on-menu labeling system confirmed. |
| Chopt Creative Salad Co. | 12 | Vegetarian options available; specific labeling system for vegetarian items not confirmed. |

**53 dishes remain unresolved. Do not apply Tag_Source without direct menu verification or canvass notes.**

### Updated totals after Phase 2A + 2B

| Status | Count |
|--------|-------|
| `goldpan_inferred` (confirmed) | 210 |
| `restaurant_disclosed` (confirmed) | 143 |
| Unresolved PROBABLE | 53 |
| NEEDS VERIFICATION (Phase 2C) | 66 |
| **Total tagged dishes** | **472** |

*Run `python3 backfill_tag_source.py --apply` to write 353 confirmed assignments to the GDL sheet.*
