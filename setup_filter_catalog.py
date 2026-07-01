"""
setup_filter_catalog.py
Creates (or overwrites) the "Filter Catalog" tab in the Goldpan Google Sheet.

Columns:
  Tag_ID               — slug used in dishes.json tags array (e.g. "halal")
  Label                — human-readable display name (e.g. "Halal")
  Category             — grouping (e.g. "Religious & Cultural")
  Definition           — one-sentence canvassing guide
  Requires_Verification — TRUE = restaurant must confirm in writing before tag is applied
  Active               — FALSE until enough verified data exists; flip to TRUE to surface in UI
  Priority             — 1–20 for launch priority list, blank otherwise
  Notes                — additional canvassing guidance

Usage:
    python3 setup_filter_catalog.py
"""

import gspread
from google.oauth2.service_account import Credentials

KEY_FILE       = "service_account.json"
SPREADSHEET_ID = "1-LiUlACSAmHLiPpF_o52gmN8AH6MfzTBktZn_R7fyQE"
TAB_NAME       = "Filter Catalog"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Tag_ID", "Label", "Category", "Definition",
    "Requires_Verification", "Active", "Priority", "Notes"
]

# (Tag_ID, Label, Category, Definition, Requires_Verification, Active, Priority, Notes)
FILTERS = [

    # ── Dietary Preferences ───────────────────────────────────────────────────
    ("vegan",           "Vegan",            "Dietary Preferences",
     "Dish contains no animal products whatsoever — no meat, poultry, seafood, dairy, eggs, honey, or animal-derived additives.",
     "FALSE", "TRUE", "", "Already active. Confirm no hidden animal ingredients (butter, gelatin, whey)."),

    ("vegetarian",      "Vegetarian",       "Dietary Preferences",
     "Dish contains no meat, poultry, or seafood but may include dairy and/or eggs.",
     "FALSE", "TRUE", "", "Already active. Watch for meat-based broths or stocks used in cooking."),

    ("plant-based",     "Plant-Based",      "Dietary Preferences",
     "Dish is made primarily or entirely from whole plant foods; may overlap with vegan but focuses on minimally processed ingredients.",
     "FALSE", "FALSE", "", "Distinct from vegan — a plant-based dish may still avoid all processed ingredients. Confirm with restaurant."),

    ("pescatarian",     "Pescatarian",      "Dietary Preferences",
     "Dish is free of meat and poultry but may contain fish or seafood.",
     "FALSE", "FALSE", "", "Tag when dish is meat-free but includes seafood as the protein."),

    ("flexitarian",     "Flexitarian",      "Dietary Preferences",
     "Dish is primarily plant-based but may include small amounts of animal products.",
     "FALSE", "FALSE", "", "Rarely applied at dish level; better as a restaurant-level tag."),

    ("keto",            "Keto",             "Dietary Preferences",
     "Dish is very low in net carbohydrates (generally under 10g per serving) and high in fat, suitable for a ketogenic diet.",
     "FALSE", "FALSE", "", "Requires nutrition data to verify carb count — do not tag based on ingredients alone."),

    ("paleo",           "Paleo",            "Dietary Preferences",
     "Dish avoids grains, legumes, dairy, refined sugar, and processed oils; focuses on meat, fish, vegetables, fruits, nuts, and seeds.",
     "FALSE", "FALSE", "", "Check for hidden grains (sauces, coatings) and legumes (peas, peanuts)."),

    ("mediterranean",   "Mediterranean",    "Dietary Preferences",
     "Dish follows Mediterranean dietary principles: olive oil, vegetables, legumes, whole grains, fish, and limited red meat.",
     "FALSE", "FALSE", "", "Loose category — use only when restaurant explicitly markets the dish this way."),

    ("whole30",         "Whole30",          "Dietary Preferences",
     "Dish contains no added sugar, alcohol, grains, legumes, dairy, or additives permitted under Whole30 guidelines.",
     "TRUE",  "FALSE", "", "Very strict — requires restaurant confirmation. Do not self-assign from menu text alone."),

    ("low-carb",        "Low-Carb",         "Dietary Preferences",
     "Dish is notably low in carbohydrates (typically under 20g net carbs per serving) but not as strict as keto.",
     "FALSE", "FALSE", "", "Use when nutrition info is available or restaurant explicitly markets it as low-carb."),

    ("carnivore",       "Carnivore",        "Dietary Preferences",
     "Dish consists entirely of animal products — meat, fish, eggs, or certain dairy — with no plant ingredients.",
     "FALSE", "FALSE", "", "Rare. Only tag if dish truly has zero plant ingredients."),

    ("raw-vegan",       "Raw Vegan",        "Dietary Preferences",
     "Dish is vegan and has not been heated above 118°F (48°C), preserving raw food diet standards.",
     "TRUE",  "FALSE", "", "Requires preparation method confirmation from restaurant."),

    # ── Religious & Cultural ──────────────────────────────────────────────────
    ("halal",           "Halal",            "Religious & Cultural",
     "Dish and all its ingredients comply with Islamic dietary law — no pork, no alcohol, and meat must be slaughtered according to halal standards.",
     "TRUE",  "FALSE", "1", "PRIORITY 1. Requires written restaurant confirmation or certified halal sourcing documentation. Do not infer from menu."),

    ("kosher",          "Kosher",           "Religious & Cultural",
     "Dish complies with Jewish dietary law — no pork, no shellfish, no mixing of meat and dairy, and meat must be from a certified kosher source.",
     "TRUE",  "FALSE", "2", "PRIORITY 2. Requires kosher certification from the restaurant. Cannot be self-assigned from menu text."),

    ("no-pork",         "No Pork",          "Religious & Cultural",
     "Dish contains no pork, ham, bacon, lard, prosciutto, pancetta, or any other porcine ingredient.",
     "FALSE", "TRUE", "", "Already active. Check hidden ingredients: lard in pastry, pork-based broths, gelatin."),

    ("no-beef",         "No Beef",          "Religious & Cultural",
     "Dish contains no beef or beef-derived ingredients, suitable for those avoiding beef for religious, cultural, or personal reasons.",
     "FALSE", "FALSE", "3", "PRIORITY 3. Check broths, stocks, and sauces for hidden beef ingredients."),

    ("no-alcohol",      "No Alcohol",       "Religious & Cultural",
     "Dish contains no alcohol or alcohol-derived ingredients, including wine reductions, beer batters, or spirits used in cooking.",
     "FALSE", "FALSE", "", "Check sauces, marinades, and desserts — alcohol is commonly used in cooking and may not be listed on menus."),

    ("hindu-friendly",  "Hindu-Friendly",   "Religious & Cultural",
     "Dish contains no beef or beef-derived ingredients and is appropriate for those following Hindu dietary practices.",
     "FALSE", "FALSE", "", "Overlaps with No Beef — may also exclude certain other meats depending on tradition. Use conservatively."),

    ("jain-friendly",   "Jain-Friendly",    "Religious & Cultural",
     "Dish excludes meat, fish, eggs, and root vegetables (onion, garlic, potatoes, carrots, beets) per Jain dietary principles.",
     "TRUE",  "FALSE", "", "Very strict. Requires restaurant confirmation. Garlic and onion in sauces will disqualify."),

    ("buddhist-friendly","Buddhist-Friendly","Religious & Cultural",
     "Dish avoids meat and often avoids garlic, onions, leeks, and other pungent vegetables per certain Buddhist dietary traditions.",
     "TRUE",  "FALSE", "", "Varies significantly by tradition. Use only when restaurant explicitly identifies dishes this way."),

    # ── Allergens & Sensitivities ─────────────────────────────────────────────
    ("gluten-free",     "Gluten Free",      "Allergens & Sensitivities",
     "Dish contains no gluten-containing ingredients (wheat, barley, rye, most oats) and is prepared to avoid cross-contamination.",
     "FALSE", "TRUE", "", "Already active. Confirm preparation method — shared fryers and surfaces may introduce gluten."),

    ("wheat-free",      "Wheat Free",       "Allergens & Sensitivities",
     "Dish contains no wheat or wheat derivatives, though may still contain other gluten sources such as barley or rye.",
     "FALSE", "FALSE", "4", "PRIORITY 4. Distinct from gluten-free — a wheat-free dish may still contain barley malt or rye."),

    ("corn-free",       "Corn Free",        "Allergens & Sensitivities",
     "Dish contains no corn or corn-derived ingredients, including corn starch, corn syrup, cornmeal, or modified corn starch.",
     "FALSE", "FALSE", "5", "PRIORITY 5. Corn is pervasive — check sauces, coatings, dressings, and sweeteners carefully."),

    ("oat-free",        "Oat Free",         "Allergens & Sensitivities",
     "Dish contains no oats or oat-derived ingredients.",
     "FALSE", "FALSE", "6", "PRIORITY 6. Often relevant for celiac sufferers since oats are frequently cross-contaminated with wheat."),

    ("dairy-free",      "Dairy Free",       "Allergens & Sensitivities",
     "Dish contains no milk, cheese, butter, cream, yogurt, or any other dairy-derived ingredient.",
     "FALSE", "TRUE", "", "Already active as No Dairy. Check hidden dairy: casein, whey, lactose in sauces and seasonings."),

    ("lactose-free",    "Lactose Free",     "Allergens & Sensitivities",
     "Dish contains no lactose but may contain other dairy components such as hard cheeses or lactose-free dairy products.",
     "FALSE", "FALSE", "", "Distinct from dairy-free — lactose-free diners can often tolerate butter and aged cheeses."),

    ("egg-free",        "Egg Free",         "Allergens & Sensitivities",
     "Dish contains no eggs or egg-derived ingredients, including mayonnaise, egg wash, or albumin.",
     "FALSE", "TRUE", "", "Already active as No Eggs. Watch for egg in pasta, coatings, sauces, and baked items."),

    ("soy-free",        "Soy Free",         "Allergens & Sensitivities",
     "Dish contains no soy or soy-derived ingredients, including soy sauce, tofu, tempeh, edamame, or soybean oil.",
     "FALSE", "TRUE", "", "Already active as No Soy. Soy is in many sauces and marinades — check carefully."),

    ("peanut-free",     "Peanut Free",      "Allergens & Sensitivities",
     "Dish contains no peanuts or peanut-derived ingredients and is prepared in an environment that avoids peanut cross-contact.",
     "FALSE", "FALSE", "8", "PRIORITY 8. Life-threatening allergen. Requires preparation environment confirmation from restaurant."),

    ("tree-nut-free",   "Tree Nut Free",    "Allergens & Sensitivities",
     "Dish contains no tree nuts (almonds, cashews, walnuts, pecans, pistachios, etc.) or tree nut-derived oils or flours.",
     "FALSE", "FALSE", "9", "PRIORITY 9. Life-threatening allergen. Requires preparation environment confirmation from restaurant."),

    ("sesame-free",     "Sesame Free",      "Allergens & Sensitivities",
     "Dish contains no sesame seeds, sesame oil, tahini, or sesame-derived ingredients.",
     "FALSE", "FALSE", "7", "PRIORITY 7. Now a major allergen in the US. Hidden in sauces, dressings, and coatings."),

    ("fish-free",       "Fish Free",        "Allergens & Sensitivities",
     "Dish contains no fish or fish-derived ingredients, including fish sauce, Worcestershire sauce, and anchovies.",
     "FALSE", "TRUE", "", "Already active as No Fish. Fish sauce is a common hidden ingredient in many cuisines."),

    ("shellfish-free",  "Shellfish Free",   "Allergens & Sensitivities",
     "Dish contains no shellfish (shrimp, crab, lobster, clams, oysters, scallops) or shellfish-derived ingredients.",
     "FALSE", "TRUE", "", "Already active as No Shellfish."),

    ("coconut-free",    "Coconut Free",     "Allergens & Sensitivities",
     "Dish contains no coconut or coconut-derived ingredients, including coconut oil, coconut milk, or desiccated coconut.",
     "FALSE", "FALSE", "", "Coconut is classified as a tree nut by the FDA — relevant for tree nut allergy sufferers."),

    ("mustard-free",    "Mustard Free",     "Allergens & Sensitivities",
     "Dish contains no mustard seeds, mustard oil, or mustard-derived condiments.",
     "FALSE", "FALSE", "", "Major allergen in EU and Canada. Hidden in dressings, marinades, and spice blends."),

    ("celery-free",     "Celery Free",      "Allergens & Sensitivities",
     "Dish contains no celery, celeriac, or celery-derived ingredients including celery salt and celery seed.",
     "FALSE", "FALSE", "", "Major allergen in EU. Found in soups, stocks, sauces, and spice blends."),

    ("lupin-free",      "Lupin Free",       "Allergens & Sensitivities",
     "Dish contains no lupin (a legume related to peanuts) or lupin flour, sometimes used in gluten-free baking.",
     "FALSE", "FALSE", "", "Emerging allergen — cross-reactive with peanut allergy. Rarely listed on menus; requires direct restaurant inquiry."),

    ("sulfite-free",    "Sulfite Free",     "Allergens & Sensitivities",
     "Dish contains no sulfites or sulfur dioxide, commonly used as preservatives in dried fruit, wine, and some condiments.",
     "TRUE",  "FALSE", "", "Requires restaurant confirmation — sulfites are often in processed ingredients and not always visible on menus."),

    ("mollusk-free",    "Mollusk Free",     "Allergens & Sensitivities",
     "Dish contains no mollusks (squid, octopus, clams, oysters, mussels, scallops, snails) or mollusk-derived ingredients.",
     "FALSE", "FALSE", "", "Distinct from shellfish-free for those with specific mollusk allergies."),

    # ── Ingredient Preferences ────────────────────────────────────────────────
    ("seed-oil-free",   "Seed Oil Free",    "Ingredient Preferences",
     "Dish is cooked without seed or vegetable oils (canola, soybean, sunflower, corn, cottonseed, grapeseed, safflower) — uses butter, olive oil, coconut oil, or animal fats instead.",
     "FALSE", "FALSE", "12", "PRIORITY 12. Increasingly requested. Requires direct restaurant inquiry about cooking oils."),

    ("organic",         "Organic Ingredients","Ingredient Preferences",
     "Key ingredients in the dish are certified organic.",
     "TRUE",  "FALSE", "16", "PRIORITY 16. Requires certification documentation from restaurant. Do not infer from menu language."),

    ("grass-fed",       "Grass-Fed",        "Ingredient Preferences",
     "Meat in the dish comes from animals raised on a grass-fed diet.",
     "TRUE",  "FALSE", "17", "PRIORITY 17. Requires restaurant sourcing confirmation. 'Grass-fed' on a menu is not sufficient — verify with supplier documentation."),

    ("pasture-raised",  "Pasture-Raised",   "Ingredient Preferences",
     "Animal products in the dish come from animals raised on open pasture.",
     "TRUE",  "FALSE", "", "Requires restaurant sourcing confirmation."),

    ("wild-caught",     "Wild-Caught",      "Ingredient Preferences",
     "Seafood in the dish is wild-caught rather than farmed.",
     "TRUE",  "FALSE", "18", "PRIORITY 18. Requires restaurant sourcing confirmation. Menu claim is acceptable starting point."),

    ("cage-free",       "Cage-Free",        "Ingredient Preferences",
     "Eggs or poultry in the dish come from cage-free animals.",
     "TRUE",  "FALSE", "", "Requires restaurant sourcing confirmation."),

    ("non-gmo",         "Non-GMO",          "Ingredient Preferences",
     "Key ingredients in the dish are non-GMO certified.",
     "TRUE",  "FALSE", "", "Requires Non-GMO Project verification or equivalent certification from restaurant."),

    ("no-artificial-colors","No Artificial Colors","Ingredient Preferences",
     "Dish contains no artificial food colorings or dyes.",
     "FALSE", "FALSE", "", "Check ingredient labels on sauces and processed components — many contain FD&C dyes."),

    ("no-artificial-flavors","No Artificial Flavors","Ingredient Preferences",
     "Dish contains no artificial flavor compounds — all flavoring comes from natural sources.",
     "FALSE", "FALSE", "", "Hidden in sauces, seasonings, and packaged ingredients. Requires ingredient-level review."),

    ("no-artificial-sweeteners","No Artificial Sweeteners","Ingredient Preferences",
     "Dish contains no artificial sweeteners (aspartame, sucralose, saccharin, acesulfame-K, etc.).",
     "FALSE", "FALSE", "", "Check beverages and dressings — common in low-calorie options."),

    ("no-preservatives","No Preservatives", "Ingredient Preferences",
     "Dish contains no chemical preservatives (BHA, BHT, sodium benzoate, nitrates, sulfites, etc.).",
     "FALSE", "FALSE", "", "Difficult to verify without full ingredient lists. Prioritize dishes made from whole, fresh ingredients."),

    ("no-hfcs",         "No High Fructose Corn Syrup","Ingredient Preferences",
     "Dish contains no high fructose corn syrup.",
     "FALSE", "FALSE", "", "Common in sauces, dressings, marinades, and baked goods. Check all packaged ingredients."),

    ("no-msg",          "No MSG",           "Ingredient Preferences",
     "Dish contains no added monosodium glutamate.",
     "FALSE", "FALSE", "", "MSG may appear under alternative names: yeast extract, hydrolyzed protein, autolyzed yeast. Requires full ingredient review."),

    ("no-nitrates",     "No Nitrates/Nitrites","Ingredient Preferences",
     "Dish contains no added nitrates or nitrites, commonly used in cured and processed meats.",
     "FALSE", "FALSE", "", "Found in bacon, ham, deli meats, hot dogs, and some smoked fish. Check all cured meat ingredients."),

    ("locally-sourced", "Locally Sourced",  "Ingredient Preferences",
     "Key ingredients in the dish are sourced from local producers within the greater Birmingham/Alabama region.",
     "TRUE",  "FALSE", "", "Requires restaurant confirmation with named local suppliers."),

    ("seasonal",        "Seasonal Ingredients","Ingredient Preferences",
     "Dish features ingredients that are currently in season and may change based on availability.",
     "FALSE", "FALSE", "", "Tag at restaurant level if menu rotates seasonally rather than at individual dish level."),

    # ── Nutrition Goals ───────────────────────────────────────────────────────
    ("high-protein",    "High Protein",     "Nutrition Goals",
     "Dish provides a high amount of protein per serving, generally 25g or more.",
     "FALSE", "TRUE", "13", "PRIORITY 13. Already active. Apply based on protein-rich primary ingredients (meat, fish, legumes, eggs) when nutrition data is unavailable."),

    ("high-fiber",      "High Fiber",       "Nutrition Goals",
     "Dish is a good source of dietary fiber, generally 5g or more per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data to verify. Beans, lentils, whole grains, and vegetables are strong indicators."),

    ("low-sugar",       "Low Sugar",        "Nutrition Goals",
     "Dish contains minimal added or natural sugars, generally under 5g per serving.",
     "FALSE", "FALSE", "14", "PRIORITY 14. Requires nutrition data. Do not tag based on appearance — sauces and dressings often contain significant sugar."),

    ("low-sodium",      "Low Sodium",       "Nutrition Goals",
     "Dish is low in sodium, generally under 600mg per serving.",
     "FALSE", "FALSE", "15", "PRIORITY 15. Requires nutrition data. Restaurant meals are frequently high in sodium — do not assume."),

    ("low-fat",         "Low Fat",          "Nutrition Goals",
     "Dish is low in total fat, generally under 10g per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data."),

    ("healthy-fats",    "Healthy Fats",     "Nutrition Goals",
     "Dish is rich in unsaturated fats from sources such as olive oil, avocado, nuts, or fatty fish.",
     "FALSE", "FALSE", "", "Tag based on primary fat sources in the dish."),

    ("high-iron",       "High Iron",        "Nutrition Goals",
     "Dish is a good source of iron, generally providing 20% or more of the daily value per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data. Red meat, legumes, spinach, and fortified grains are strong indicators."),

    ("high-calcium",    "High Calcium",     "Nutrition Goals",
     "Dish is a good source of calcium, generally providing 20% or more of the daily value per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data."),

    ("high-potassium",  "High Potassium",   "Nutrition Goals",
     "Dish is a good source of potassium, generally providing 700mg or more per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data."),

    ("high-vitamin-d",  "High Vitamin D",   "Nutrition Goals",
     "Dish is a good source of vitamin D, generally providing 20% or more of the daily value per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data. Fatty fish, egg yolks, and fortified foods are primary sources."),

    ("high-omega3",     "High Omega-3",     "Nutrition Goals",
     "Dish is rich in omega-3 fatty acids from sources such as fatty fish, flaxseed, walnuts, or chia seeds.",
     "FALSE", "FALSE", "", "Tag based on primary ingredients. Salmon, mackerel, sardines, and walnuts are strong indicators."),

    ("low-cholesterol", "Low Cholesterol",  "Nutrition Goals",
     "Dish is low in dietary cholesterol, generally under 100mg per serving.",
     "FALSE", "FALSE", "", "Requires nutrition data."),

    ("heart-healthy",   "Heart Healthy",    "Nutrition Goals",
     "Dish supports cardiovascular health — low in saturated fat, sodium, and cholesterol while being rich in fiber, healthy fats, or omega-3s.",
     "FALSE", "FALSE", "", "Composite tag — use only when multiple heart-healthy indicators are confirmed."),

    ("diabetic-friendly","Diabetic Friendly","Nutrition Goals",
     "Dish is appropriate for people managing blood sugar — low in refined carbohydrates, added sugar, and high-glycemic ingredients.",
     "FALSE", "FALSE", "", "Requires nutrition data. Do not tag based on appearance alone. Consult glycemic index of primary ingredients."),

    # ── Preparation & Cooking ─────────────────────────────────────────────────
    ("grilled",         "Grilled",          "Preparation & Cooking",
     "Dish is prepared using direct dry heat on a grill grate over gas, charcoal, or electric heat.",
     "FALSE", "FALSE", "", "Can be tagged from menu text when preparation method is explicitly stated."),

    ("baked",           "Baked",            "Preparation & Cooking",
     "Dish is cooked using dry heat in an oven.",
     "FALSE", "FALSE", "", ""),

    ("steamed",         "Steamed",          "Preparation & Cooking",
     "Dish is cooked using steam heat with no direct contact with water or oil.",
     "FALSE", "FALSE", "", ""),

    ("roasted",         "Roasted",          "Preparation & Cooking",
     "Dish is cooked using dry oven heat, typically at high temperature to develop browning.",
     "FALSE", "FALSE", "", ""),

    ("fried",           "Fried",            "Preparation & Cooking",
     "Dish is cooked by submerging or partial-submerging in hot oil.",
     "FALSE", "FALSE", "", ""),

    ("air-fried",       "Air Fried",        "Preparation & Cooking",
     "Dish is prepared using an air fryer — circulated hot air with minimal or no oil.",
     "FALSE", "FALSE", "", "Relevant for customers avoiding fried foods but willing to eat air-fried options."),

    ("smoked",          "Smoked",           "Preparation & Cooking",
     "Dish is cooked and/or flavored using wood smoke.",
     "FALSE", "FALSE", "", ""),

    ("charcoal-grilled","Charcoal Grilled", "Preparation & Cooking",
     "Dish is grilled specifically over charcoal rather than gas or electric heat.",
     "FALSE", "FALSE", "", ""),

    ("wood-fired",      "Wood Fired",       "Preparation & Cooking",
     "Dish is cooked in a wood-fired oven or over an open wood fire.",
     "FALSE", "FALSE", "", ""),

    ("cooked-in-butter","Cooked in Butter", "Preparation & Cooking",
     "Dish is prepared using butter as the primary cooking fat.",
     "FALSE", "FALSE", "", "Relevant for dairy-free and vegan diners — flag accordingly."),

    ("cooked-in-olive-oil","Cooked in Olive Oil","Preparation & Cooking",
     "Dish is prepared using olive oil as the primary cooking fat.",
     "FALSE", "FALSE", "", "Relevant for seed oil-free diners."),

    ("seed-oil-free-prep","Seed Oil Free Preparation","Preparation & Cooking",
     "Dish is cooked without seed or vegetable oils — restaurant uses butter, olive oil, coconut oil, lard, or tallow.",
     "TRUE",  "FALSE", "", "Requires restaurant confirmation of cooking oil used. Critical for seed oil-free filter."),

    ("separate-fryer",  "Separate Fryer Available","Preparation & Cooking",
     "Restaurant has a dedicated fryer for this dish that is not shared with allergen-containing foods (e.g. gluten-free fryer).",
     "TRUE",  "FALSE", "19", "PRIORITY 19. Life-critical for celiac and severe allergen sufferers. Requires direct restaurant confirmation."),

    ("cross-contamination-conscious","Cross-Contamination Conscious","Preparation & Cooking",
     "Restaurant takes documented steps to prevent cross-contamination for specific allergens during preparation.",
     "TRUE",  "FALSE", "20", "PRIORITY 20. Requires restaurant confirmation of specific protocols. Be specific about which allergen is protected."),

    # ── Lifestyle & Wellness ──────────────────────────────────────────────────
    ("pregnancy-friendly","Pregnancy Friendly","Lifestyle & Wellness",
     "Dish avoids ingredients not recommended during pregnancy: raw or undercooked meat/fish/eggs, high-mercury fish, unpasteurized dairy, and excess caffeine.",
     "FALSE", "FALSE", "", "Requires thorough ingredient and preparation review. Err on the side of caution."),

    ("kid-friendly",    "Kid Friendly",     "Lifestyle & Wellness",
     "Dish is mild in flavor, appropriately sized or portionable, and made with ingredients generally accepted by children.",
     "FALSE", "FALSE", "", ""),

    ("athlete-friendly","Athlete Friendly", "Lifestyle & Wellness",
     "Dish is high in quality protein and complex carbohydrates, suitable for fueling athletic performance.",
     "FALSE", "FALSE", "", ""),

    ("bodybuilding",    "Bodybuilding",     "Lifestyle & Wellness",
     "Dish is very high in protein (35g+) with controlled fat and carbohydrate content, suitable for muscle-building goals.",
     "FALSE", "FALSE", "", "Requires nutrition data to verify macros."),

    ("weight-loss",     "Weight Loss",      "Lifestyle & Wellness",
     "Dish is lower in calories, refined carbohydrates, and unhealthy fats while being satiating.",
     "FALSE", "FALSE", "", "Requires nutrition data. Do not tag based on subjective appearance."),

    ("muscle-gain",     "Muscle Gain",      "Lifestyle & Wellness",
     "Dish provides high protein and sufficient calories to support muscle hypertrophy.",
     "FALSE", "FALSE", "", "Overlaps with High Protein and Bodybuilding."),

    ("anti-inflammatory","Anti-Inflammatory","Lifestyle & Wellness",
     "Dish features ingredients known for anti-inflammatory properties: omega-3 rich foods, turmeric, ginger, berries, leafy greens, and olive oil.",
     "FALSE", "FALSE", "", "Tag based on primary ingredients. Avoid dishes with refined sugars, seed oils, or processed meats."),

    ("gut-friendly",    "Gut Friendly",     "Lifestyle & Wellness",
     "Dish supports digestive health — includes probiotics, prebiotics, fermented foods, or fiber-rich ingredients.",
     "FALSE", "FALSE", "", ""),

    ("ibs-friendly",    "IBS Friendly",     "Lifestyle & Wellness",
     "Dish is appropriate for people with Irritable Bowel Syndrome — generally low-FODMAP, low in insoluble fiber, and easy to digest.",
     "FALSE", "FALSE", "10", "PRIORITY 10. Highly requested. Overlaps with Low-FODMAP — confirm with Low-FODMAP guidelines."),

    ("low-fodmap",      "Low FODMAP",       "Lifestyle & Wellness",
     "Dish is low in fermentable oligosaccharides, disaccharides, monosaccharides, and polyols — ingredients that trigger IBS symptoms.",
     "FALSE", "FALSE", "11", "PRIORITY 11. Specific and verifiable. Consult Monash University FODMAP app for ingredient guidance."),

    ("gerd-friendly",   "GERD Friendly",    "Lifestyle & Wellness",
     "Dish avoids common acid reflux triggers: tomatoes, citrus, spicy foods, fried foods, caffeine, chocolate, and onion/garlic.",
     "FALSE", "FALSE", "", "Requires full ingredient review. Many common restaurant ingredients are GERD triggers."),

    # ── Spice & Flavor ────────────────────────────────────────────────────────
    ("mild",            "Mild",             "Spice & Flavor",
     "Dish has little to no spice heat — suitable for those with low spice tolerance.",
     "FALSE", "FALSE", "", ""),

    ("medium",          "Medium",           "Spice & Flavor",
     "Dish has a moderate level of spice heat.",
     "FALSE", "FALSE", "", ""),

    ("spicy",           "Spicy",            "Spice & Flavor",
     "Dish has a noticeable and significant level of spice heat.",
     "FALSE", "FALSE", "", ""),

    ("very-spicy",      "Very Spicy",       "Spice & Flavor",
     "Dish is intensely spicy — may be too hot for those unaccustomed to high heat.",
     "FALSE", "FALSE", "", ""),

    ("sweet",           "Sweet",            "Spice & Flavor",
     "Dish has a predominantly sweet flavor profile.",
     "FALSE", "FALSE", "", ""),

    ("savory",          "Savory",           "Spice & Flavor",
     "Dish has a predominantly savory, umami-forward flavor profile.",
     "FALSE", "FALSE", "", ""),

    # ── Sustainability & Ethics ───────────────────────────────────────────────
    ("sustainable-seafood","Sustainable Seafood","Sustainability & Ethics",
     "Seafood in the dish is sourced from sustainable fisheries, verified by certification such as MSC, Seafood Watch, or equivalent.",
     "TRUE",  "FALSE", "", "Requires restaurant sourcing confirmation or certification documentation."),

    ("humanely-raised", "Humanely Raised",  "Sustainability & Ethics",
     "Animal products in the dish come from animals raised under humane conditions, verified by a recognized animal welfare certification.",
     "TRUE",  "FALSE", "", "Requires certification documentation (e.g. Certified Humane, Animal Welfare Approved)."),

    ("fair-trade",      "Fair Trade Ingredients","Sustainability & Ethics",
     "Key ingredients (coffee, chocolate, sugar, etc.) are Fair Trade certified.",
     "TRUE",  "FALSE", "", "Requires Fair Trade certification documentation from restaurant."),

    ("locally-owned",   "Locally Owned Restaurant","Sustainability & Ethics",
     "The restaurant is independently and locally owned, not a franchise or national chain.",
     "FALSE", "FALSE", "", "Tag at restaurant level, not dish level."),

    ("eco-packaging",   "Eco-Friendly Packaging","Sustainability & Ethics",
     "Restaurant uses compostable, recyclable, or minimal packaging for this dish.",
     "TRUE",  "FALSE", "", "Relevant for takeout/delivery. Requires restaurant confirmation."),

    # ── Transparency (Goldpan Differentiator) ─────────────────────────────────
    ("has-ingredients",  "Has Full Ingredient List","Transparency",
     "Dish has a complete list of ingredients publicly disclosed on the menu or by the restaurant.",
     "FALSE", "TRUE", "", "Already active as Has Ingredients."),

    ("has-allergens",    "Has Allergen Information","Transparency",
     "Restaurant has disclosed allergen information for this dish.",
     "FALSE", "TRUE", "", "Already active as Has Allergen Info."),

    ("has-dietary",      "Has Dietary Information","Transparency",
     "Restaurant has disclosed dietary classification information for this dish (vegan, gluten-free, etc.).",
     "FALSE", "TRUE", "", "Already active as Has Dietary Info."),

    ("has-nutrition",    "Has Nutrition Information","Transparency",
     "Restaurant has publicly disclosed calorie count and/or macro/micronutrient data for this dish.",
     "FALSE", "FALSE", "", "Tag when full or partial nutrition panel is available from the restaurant."),

    ("prep-disclosed",   "Preparation Method Disclosed","Transparency",
     "Restaurant has publicly described how this dish is prepared (grilled, baked, fried, etc.).",
     "FALSE", "FALSE", "", ""),

    ("sourcing-disclosed","Sourcing Information Available","Transparency",
     "Restaurant has publicly disclosed where key ingredients are sourced from.",
     "FALSE", "FALSE", "", ""),

    ("restaurant-verified","Restaurant Verified","Transparency",
     "A restaurant representative has reviewed and confirmed the Goldpan data for this dish.",
     "TRUE",  "FALSE", "", "Highest trust level. Requires documented confirmation from the restaurant."),

    ("recently-updated", "Recently Updated", "Transparency",
     "Dish data has been verified or updated within the last 90 days.",
     "FALSE", "FALSE", "", "System tag — set automatically by recanvass pipeline."),

    ("high-transparency","High Transparency","Transparency",
     "Dish meets Goldpan's High Transparency standard across all four dimensions: ingredients, sauces, allergens, and preparation.",
     "FALSE", "TRUE", "", "Already active. Assigned by scoring pipeline."),

    ("moderate-transparency","Moderate Transparency","Transparency",
     "Dish meets Goldpan's Moderate Transparency standard with strong but incomplete disclosure.",
     "FALSE", "TRUE", "", "Already active. Assigned by scoring pipeline."),

    ("building-transparency","Building Transparency","Transparency",
     "Dish is at the Building Transparency level — partial disclosure with significant gaps remaining.",
     "FALSE", "TRUE", "", "Already active. Assigned by scoring pipeline."),
]


def main():
    creds  = Credentials.from_service_account_file(KEY_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss     = client.open_by_key(SPREADSHEET_ID)

    # Create or clear the tab
    try:
        ws = ss.worksheet(TAB_NAME)
        ws.clear()
        print(f"Cleared existing '{TAB_NAME}' tab.")
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_NAME, rows=300, cols=len(HEADERS))
        print(f"Created new '{TAB_NAME}' tab.")

    # Write header
    ws.append_row(HEADERS)

    # Write all filters
    rows = []
    for f in FILTERS:
        rows.append(list(f))

    ws.append_rows(rows, value_input_option="RAW")

    # Format header row bold
    ws.format("A1:H1", {"textFormat": {"bold": True}})

    # Freeze header row
    ss.batch_update({"requests": [{"updateSheetProperties": {
        "properties": {"sheetId": ws.id, "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount"
    }}]})

    print(f"\n✅ Filter Catalog complete — {len(FILTERS)} tags written to '{TAB_NAME}'.")
    print(f"   Priority tags: {sum(1 for f in FILTERS if f[6])}")
    print(f"   Verification required: {sum(1 for f in FILTERS if f[4] == 'TRUE')}")
    print(f"   Already active: {sum(1 for f in FILTERS if f[5] == 'TRUE')}")


if __name__ == "__main__":
    main()
