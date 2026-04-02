import re

def build():
    with open("listintel_landing_final.html", "r", encoding="utf-8") as f:
        final_html = f.read()

    with open("listintel_landing_v4.html", "r", encoding="utf-8") as f:
        v4_html = f.read()

    # Extract ALL styles from final_html
    style_match_final = re.search(r"<style>(.*?)</style>", final_html, re.DOTALL)
    styles_final = style_match_final.group(1) if style_match_final else ""

    # Extract ALL styles from v4_html
    style_match_v4 = re.search(r"<style>(.*?)</style>", v4_html, re.DOTALL)
    styles_v4 = style_match_v4.group(1) if style_match_v4 else ""

    # Combine styles. We'll put v4 first, then final so the hero and float animations override properly.
    # But wait, final also has styles for the older body format. 
    # Actually, let's just use final's styles entirely and append only the v4 dark integration styles that are missing!
    # "v4 contains 'INTEGRATIONS DARK' block" -> look for #integrations in v4
    v4_int_dark = re.search(r"(/\* INTEGRATIONS DARK \*/.*?)/\* PRICING \*/", styles_v4, re.DOTALL)
    v4_integration_styles = v4_int_dark.group(1) if v4_int_dark else ""

    # Add features styles from v4 if they differ? No, the user said v4 for the REST of the site.
    # It is safer just to output <style>{v4_styles}\n{final_extra_hero_styles}</style>.
    # Let's extract the floating and hero specific CSS from final_html.
    floaters_css = re.search(r"(/\* FLOATERS \*/.*?)(\n/\* EXCEL CARD \*/)", styles_final, re.DOTALL)
    hero_css = re.search(r"(/\* HERO \*/.*?)(\n/\* FLOATERS \*/)", styles_final, re.DOTALL)
    
    # Let's just create one cohesive css:
    combined_css = f"{styles_v4}\n\n/* HERO MODS FROM FINAL */\n{hero_css.group(1) if hero_css else ''}\n\n/* FLOATERS FROM FINAL */\n{floaters_css.group(1) if floaters_css else ''}\n"

    # Extract NAV, HERO, EXCEL CARD from final_html
    nav_hero_excel = re.search(r"(<!-- NAV -->.*?)<!-- MARQUEE STRIP -->", final_html, re.DOTALL)
    nav_hero_excel_content = nav_hero_excel.group(1)

    # Extract from MARQUEE STRIP to end from v4_html
    marquee_to_end = re.search(r"(<!-- MARQUEE STRIP -->.*)", v4_html, re.DOTALL)
    marquee_content = marquee_to_end.group(1)

    # Replace the marquee svgs with actual actual image tags.
    # The user wants exact product logos.
    marquee_logos = """
    <div class="li"><img src="https://logo.clearbit.com/instantly.ai" style="width:20px;height:20px;border-radius:4px;" alt="Instantly" onerror="this.style.display='none'"> Instantly</div>
    <div class="li"><img src="https://logo.clearbit.com/smartlead.ai" style="width:20px;height:20px;border-radius:4px;" alt="Smartlead" onerror="this.style.display='none'"> Smartlead</div>
    <div class="li"><img src="https://logo.clearbit.com/apollo.io" style="width:20px;height:20px;border-radius:4px;" alt="Apollo" onerror="this.style.display='none'"> Apollo</div>
    <div class="li"><img src="https://logo.clearbit.com/clay.com" style="width:20px;height:20px;border-radius:4px;" alt="Clay" onerror="this.style.display='none'"> Clay</div>
    <div class="li"><img src="https://logo.clearbit.com/lemlist.com" style="width:20px;height:20px;border-radius:4px;" alt="Lemlist" onerror="this.style.display='none'"> Lemlist</div>
    <div class="li"><img src="https://logo.clearbit.com/n8n.io" style="width:20px;height:20px;border-radius:4px;" alt="n8n" onerror="this.style.display='none'"> n8n</div>
    <div class="li"><img src="https://logo.clearbit.com/hubspot.com" style="width:20px;height:20px;border-radius:4px;" alt="HubSpot" onerror="this.style.display='none'"> HubSpot</div>
    <div class="li"><img src="https://logo.clearbit.com/zapier.com" style="width:20px;height:20px;border-radius:4px;" alt="Zapier" onerror="this.style.display='none'"> Zapier</div>
    <div class="li"><img src="https://logo.clearbit.com/make.com" style="width:20px;height:20px;border-radius:4px;" alt="Make" onerror="this.style.display='none'"> Make</div>
    """
    
    # We need to duplicate it for the infinite scroll
    full_marquee_track = f'<div class="mq-inner" id="mqi">{marquee_logos}{marquee_logos}</div>'
    marquee_content = re.sub(r'<div class="mq-inner" id="mqi">.*?</div></div>', full_marquee_track + "</div>", marquee_content, flags=re.DOTALL)
    
    # Write the assembled HTML to app/templates/landing.html
    assembled_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>List Intel | Email List Intelligence</title>
    <style>
{combined_css}
    </style>
</head>
<body>
{nav_hero_excel_content}
{marquee_content}
</body>
</html>
"""

    with open("app/templates/landing.html", "w", encoding="utf-8") as f:
        f.write(assembled_html)
    
    print("Done building landing.html")

if __name__ == "__main__":
    build()
