import re

def process_landing():
    with open("listintel_landing_final.html", "r", encoding="utf-8") as f:
        hero_html = f.read()
    with open("listintel_landing_v4.html", "r", encoding="utf-8") as f:
        v4_html = f.read()

    # Extract CSS from hero
    hero_css_match = re.search(r'<style>(.*?)</style>', hero_html, re.DOTALL)
    hero_css = hero_css_match.group(1) if hero_css_match else ""

    # Extract additional CSS from V4 that might be missing (like the ones for Integrations and Pricing)
    v4_css_match = re.search(r'<style>(.*?)</style>', v4_html, re.DOTALL)
    v4_css = v4_css_match.group(1) if v4_css_match else ""

    merged_css = f"""{hero_css}

/* === V4 SPECIFIC STYLES === */
.pricing-accordion {{
    max-width: 1160px; margin: 0 auto; margin-top: 30px;
    background: #fff; border: 1px solid var(--border); border-radius: 16px;
    overflow: hidden;
}}
.pa-header {{
    padding: 24px 32px; display: flex; justify-content: space-between; align-items: center;
    cursor: pointer; user-select: none; background: #fafaf5;
}}
.pa-title {{ font-size: 18px; font-weight: 700; color: var(--text); }}
.pa-icon {{ transition: transform 0.3s; font-size: 20px; }}
.pa-content {{ padding: 0 32px; max-height: 0; overflow: hidden; transition: max-height 0.4s ease, padding 0.4s ease; }}
.pricing-accordion.open .pa-content {{ max-height: 1200px; padding: 32px; }}
.pricing-accordion.open .pa-icon {{ transform: rotate(180deg); }}

/* BLURRY PAPERS BACKGROUND */
.blurry-papers {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; overflow: hidden; z-index: 0; pointer-events: none; }}
.blurry-paper {{
    position: absolute; background: rgba(255, 255, 255, 0.85); border: 1px solid rgba(0, 0, 0, 0.05);
    box-shadow: 0 20px 60px rgba(0,0,0,0.06); padding: 40px; border-radius: 8px;
    filter: blur(5px) opacity(60%); color: #e0e0d8; font-family: monospace; font-size: 10px; line-height: 1.4;
    overflow: hidden;
}}
.bp1 {{ top: 5%; left: -5%; width: 400px; height: 500px; transform: rotate(-12deg); animation: float1 15s ease-in-out infinite alternate; }}
.bp2 {{ top: 20%; right: -10%; width: 500px; height: 600px; transform: rotate(8deg); animation: float2 18s ease-in-out infinite alternate; filter: blur(7px) opacity(50%); }}
.bp3 {{ top: 60%; left: 15%; width: 350px; height: 450px; transform: rotate(-6deg); animation: float1 20s ease-in-out infinite alternate-reverse; }}
@keyframes float1 {{ 0% {{ transform: translateY(0) rotate(-12deg); }} 100% {{ transform: translateY(-40px) rotate(-8deg); }} }}
@keyframes float2 {{ 0% {{ transform: translateY(0) rotate(8deg); }} 100% {{ transform: translateY(-50px) rotate(12deg); }} }}
"""

    # Fix hero to include blurry papers
    hero_section_match = re.search(r'(<section id="hero">.*?</section>)', hero_html, re.DOTALL)
    hero_section = hero_section_match.group(1) if hero_section_match else ""
    
    # Inject blurry papers into hero
    papers_html = """
  <div class="blurry-papers">
    <div class="blurry-paper bp1">
      {{"01010110" * 40}}<br>{{"11001010" * 40}}<br>system.out.delivery<br>hash: a3f8...c91e<br>status: OK
    </div>
    <div class="blurry-paper bp2">
      {{"11100010" * 50}}<br>connect_timeout<br>SMTP Response: 250<br>{{"00011100" * 50}}
    </div>
    <div class="blurry-paper bp3">
      {{"10101010" * 30}}<br>infra: GWS detected<br>burn_score: 95
    </div>
  </div>
"""
    hero_section = hero_section.replace('<section id="hero">', f'<section id="hero">{papers_html}')

    # Extract Features, Integrations, Stats, Footer CTA, Footer from V4
    v4_features = re.search(r'(<!-- FEATURES -->.*?)</section>', v4_html, re.DOTALL).group(1) + "</section>"
    v4_integrations = re.search(r'(<!-- INTEGRATIONS .*?)</section>', v4_html, re.DOTALL).group(1) + "</section>"
    
    # Custom Pricing Section with Accordion
    pricing_html = """
<!-- PRICING -->
<section id="pricing">
  <div class="sec-tag r">⬡ Pricing</div>
  <h2 class="r d1">Start free.<br>Scale when ready.</h2>
  <p class="sec-sub r d2">Full SaaS from day one. Paystack billing — USD globally, NGN locally.</p>
  
  <div class="pricing-accordion r d3" x-data="{ open: true }" :class="{ 'open': open }">
    <div class="pa-header" @click="open = !open">
      <div class="pa-title">View All Plans & Pricing</div>
      <div class="pa-icon">▼</div>
    </div>
    <div class="pa-content">
      <div class="pgrid">
        <div class="pcard">
          <div class="plan-name">Free</div>
          <div class="plan-price">$0</div>
          <div class="plan-period">forever</div>
          <div class="plan-credits">500 credits / month</div>
          <div class="pf inc">Syntax validation</div>
          <div class="pf inc">MX / domain check</div>
          <div class="pf inc">Spam filter detector</div>
          <div class="pf inc">Infra detector</div>
          <div class="pf">Burn score</div>
          <div class="pf">Fresh Only export</div>
          <div class="pf">Marketplace</div>
          <button class="plan-btn">Get started</button>
        </div>
        <div class="pcard d1">
          <div class="plan-name">Starter</div>
          <div class="plan-price"><sup>$</sup>19</div>
          <div class="plan-period">per month</div>
          <div class="plan-credits">25,000 credits / month</div>
          <div class="pf inc">Everything in Free</div>
          <div class="pf inc">Burn score</div>
          <div class="pf inc">Fresh Only export</div>
          <div class="pf inc">Bounce data submission</div>
          <div class="pf">Marketplace</div>
          <div class="pf">API access</div>
          <button class="plan-btn">Get started</button>
        </div>
        <div class="pcard feat d2">
          <div class="feat-badge">Most popular</div>
          <div class="plan-name">Growth</div>
          <div class="plan-price"><sup>$</sup>49</div>
          <div class="plan-period">per month</div>
          <div class="plan-credits">100,000 credits / month</div>
          <div class="pf inc">Everything in Starter</div>
          <div class="pf inc">Marketplace access</div>
          <div class="pf inc">Bounce history score</div>
          <div class="pf inc">3 team seats</div>
          <div class="pf">API access</div>
          <button class="plan-btn fb">Get started</button>
        </div>
        <div class="pcard d3">
          <div class="plan-name">Pro</div>
          <div class="plan-price"><sup>$</sup>99</div>
          <div class="plan-period">per month</div>
          <div class="plan-credits">500,000 credits / month</div>
          <div class="pf inc">Everything in Growth</div>
          <div class="pf inc">REST API access</div>
          <div class="pf inc">API key management</div>
          <div class="pf inc">10 team seats</div>
          <div class="pf inc">Priority processing</div>
          <button class="plan-btn">Get started</button>
        </div>
      </div>
    </div>
  </div>
</section>
"""
    v4_quote = re.search(r'(<!-- QUOTE -->.*?)</section>', v4_html, re.DOTALL).group(1) + "</section>"
    v4_stats = re.search(r'(<!-- STATS -->.*?</div>)', v4_html, re.DOTALL).group(1)
    v4_fcta = re.search(r'(<!-- FOOTER CTA -->.*?)</section>', v4_html, re.DOTALL).group(1) + "</section>"
    v4_footer = re.search(r'(<!-- FOOTER -->.*?</footer>)', v4_html, re.DOTALL).group(1)

    # Clean Nigeria and rewrite links to /info
    v4_footer = v4_footer.replace("<br>Built in Nigeria · Serving the world", "")
    
    footer_links = [
        ("Burn Score", "/info#burn-score"),
        ("Spam Filters", "/info#spam-filters"),
        ("Domain Age", "/info#domain-age"),
        ("Marketplace", "/info#marketplace"),
        ("REST API", "/info#rest-api"),
        ("Agencies", "/info#agencies"),
        ("Solo operators", "/info#solo-operators"),
        ("Developers", "/info#developers"),
        ("Enterprise", "/info#enterprise"),
        ("Pricing", "/info#pricing"),
        ("API Docs", "/info#api-docs"),
        ("Changelog", "/info#changelog"),
        ("Blog", "/info#blog"),
    ]
    for text, link in footer_links:
        v4_footer = re.sub(r'<a href="#">' + text + r'</a>', f'<a href="{link}">{text}</a>', v4_footer)

    # Write out app/templates/landing.html
    full_html = f"""{{% extends "base.html" %}}
{{% block title %}}List Intel — Know Before You Send{{% endblock %}}
{{% block description %}}Cold email list intelligence platform. Check burn scores, detect spam filters, verify deliverability, and trade burned lists anonymously.{{% endblock %}}

{{% block content %}}
<style>
{merged_css}
</style>

<!-- NAV -->
<nav>
  <a class="logo" href="/" style="text-decoration:none;">
    <div class="lmark">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="2" y="2" width="5" height="5" rx="1.2" fill="white" opacity=".95"/><rect x="9" y="2" width="5" height="5" rx="1.2" fill="white" opacity=".65"/><rect x="2" y="9" width="5" height="5" rx="1.2" fill="white" opacity=".65"/><rect x="9" y="9" width="5" height="5" rx="1.2" fill="white" opacity=".35"/></svg>
    </div>
    <div class="lname">List<span>Intel</span></div>
  </a>
  <div class="nlinks">
    <a href="#features">Features</a><a href="#pricing">Pricing</a><a href="/info#api-docs">API Docs</a>
  </div>
  <div class="nr">
    <a href="/auth/login" class="bgh" style="text-decoration:none;">Log In</a>
    <a href="/auth/signup" class="bcta" style="text-decoration:none;">Start for Free</a>
  </div>
</nav>

{hero_section}
{v4_features}
{v4_integrations}
{pricing_html}
{v4_quote}
{v4_stats}
{v4_fcta}
{v4_footer}

<script>
const obs = new IntersectionObserver(es => es.forEach(e => {{ if(e.isIntersecting){{e.target.classList.add('v');obs.unobserve(e.target);}}}}),{{threshold:.1}});
document.querySelectorAll('.r').forEach(el => obs.observe(el));
document.querySelectorAll('.tog').forEach(t => t.addEventListener('click',()=>{{t.classList.toggle('on');t.classList.toggle('off');}}));

// Nav transparency on scroll
const nav = document.querySelector('nav');
window.addEventListener('scroll', () => {{
  if (window.scrollY > 10) {{
    nav.style.background = 'rgba(242,241,236,.85)';
    nav.style.boxShadow = '0 4px 20px rgba(0,0,0,0.05)';
  }} else {{
    nav.style.background = 'rgba(242,241,236,.95)';
    nav.style.boxShadow = 'none';
  }}
}});
</script>
{{% endblock %}}
"""
    with open("app/templates/landing.html", "w", encoding="utf-8") as f:
        f.write(full_html)

if __name__ == "__main__":
    process_landing()
    print("landing.html created successfully.")
